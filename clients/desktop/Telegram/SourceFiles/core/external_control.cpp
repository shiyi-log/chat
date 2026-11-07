/*
This file is part of Telegram Desktop,
the official desktop application for the Telegram messaging service.

For license and copyright information please follow this link:
https://github.com/telegramdesktop/tdesktop/blob/master/LEGAL
*/
#include "core/external_control.h"

#include "core/application.h"
#include "core/core_settings.h"
#include "window/window_controller.h"
#include "ui/layers/generic_box.h"
#include "ui/widgets/buttons.h"
#include "ui/widgets/labels.h"
#include "ui/vertical_list.h"
#include "base/random.h"
#include "styles/style_boxes.h"
#include "styles/style_layers.h"
#include "styles/style_widgets.h"

#include <QtWidgets/QApplication>
#include <QtWidgets/QWidget>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>

namespace Core {
namespace {

constexpr auto kAutomationKey = std::string_view("automation.enabled");

struct WindowEntry {
	not_null<Window::Controller*> controller;
	QWidget *window = nullptr;
};

[[nodiscard]] bool AutomationEnabled() {
	return Core::App().settings().readPref<bool>(kAutomationKey, false);
}

void FillAutomationConfirmBox(
		not_null<Ui::GenericBox*> box,
		const QString &text,
		Fn<void()> enable) {
	box->setTitle(rpl::single(u"本地自动化"_q));
	box->addRow(object_ptr<Ui::FlatLabel>(
		box,
		rpl::single(text),
		st::boxLabel));

	const auto cancel = [=] {
		box->closeBox();
	};
	struct Entry {
		QString text;
		Fn<void()> callback;
	};
	auto entries = std::vector<Entry>{
		{ u"启用"_q, enable },
		{ u"取消"_q, cancel },
		{ u"不确定"_q, cancel },
	};
	for (auto i = int(entries.size()) - 1; i > 0; --i) {
		std::swap(entries[i], entries[base::RandomIndex(i + 1)]);
	}

	const auto content = box->verticalLayout();
	for (const auto &entry : entries) {
		Ui::AddSkip(content);
		const auto button = content->add(
			object_ptr<Ui::RoundButton>(
				content,
				rpl::single(entry.text),
				st::defaultLightButton),
			st::boxRowPadding,
			style::al_justify);
		button->setFullRadius(true);
		button->setClickedCallback(entry.callback);
	}
	box->setStyle(st::localAutomationBox);
}

void RequestEnableAutomation() {
	const auto window = Core::App().activePrimaryWindow();
	if (!window) {
		return;
	}
	static QPointer<Ui::GenericBox> current;
	if (current) {
		return;
	}
	const auto show = window->uiShow();

	const auto second = [=](not_null<Ui::GenericBox*> box) {
		current = box.get();
		FillAutomationConfirmBox(
			box,
			u"请再次确认是否启用本地自动化。"_q,
			[=] {
				Core::App().settings().writePref<bool>(
					kAutomationKey,
					true);
				box->closeBox();
			});
	};
	const auto first = [=](not_null<Ui::GenericBox*> box) {
		current = box.get();
		FillAutomationConfirmBox(
			box,
			u"有外部程序正通过本地套接字尝试控制 Chat 桌面端，以读取已打开的窗口并激活窗口。\n\n"
			u"启用本地自动化后，当前用户帐户下运行的程序都可以控制此应用。"_q,
			[=] {
				box->closeBox();
				show->showBox(Box(second));
			});
	};
	show->show(Box(first));
}

[[nodiscard]] QByteArray Pack(QJsonObject object) {
	return QJsonDocument(object).toJson(QJsonDocument::Compact);
}

[[nodiscard]] QByteArray Error(const QString &text) {
	auto object = QJsonObject();
	object.insert(u"ok"_q, false);
	object.insert(u"error"_q, text);
	return Pack(object);
}

[[nodiscard]] std::vector<WindowEntry> CollectWindows() {
	auto result = std::vector<WindowEntry>();
	for (const auto widget : QApplication::topLevelWidgets()) {
		const auto controller = App().findWindow(widget);
		if (!controller) {
			continue;
		}
		auto already = false;
		for (const auto &entry : result) {
			if (entry.controller.get() == controller) {
				already = true;
				break;
			}
		}
		if (!already) {
			result.push_back({ controller, widget->window() });
		}
	}
	ranges::sort(result, [](const WindowEntry &a, const WindowEntry &b) {
		if (a.controller->isPrimary() != b.controller->isPrimary()) {
			return a.controller->isPrimary();
		}
		return a.controller.get() < b.controller.get();
	});
	return result;
}

[[nodiscard]] QByteArray HandleWindows() {
	const auto active = App().activeWindow();
	auto list = QJsonArray();
	auto index = 0;
	for (const auto &entry : CollectWindows()) {
		auto object = QJsonObject();
		object.insert(u"id"_q, index++);
		object.insert(u"title"_q, entry.window->windowTitle());
		object.insert(u"primary"_q, entry.controller->isPrimary());
		object.insert(u"active"_q, (entry.controller.get() == active));
		list.append(object);
	}
	auto object = QJsonObject();
	object.insert(u"ok"_q, true);
	object.insert(u"windows"_q, list);
	return Pack(object);
}

[[nodiscard]] QByteArray HandleActivate(int index) {
	const auto windows = CollectWindows();
	if (index < 0 || index >= int(windows.size())) {
		return Error(u"no such window"_q);
	}
	windows[index].controller->activate();
	auto object = QJsonObject();
	object.insert(u"ok"_q, true);
	object.insert(u"activated"_q, index);
	return Pack(object);
}

[[nodiscard]] QByteArray HandleCycle() {
	const auto windows = CollectWindows();
	if (windows.empty()) {
		return Error(u"no windows"_q);
	}
	const auto active = App().activeWindow();
	auto current = 0;
	for (auto i = 0, count = int(windows.size()); i != count; ++i) {
		if (windows[i].controller.get() == active) {
			current = i;
			break;
		}
	}
	const auto next = (current + 1) % int(windows.size());
	windows[next].controller->activate();
	auto object = QJsonObject();
	object.insert(u"ok"_q, true);
	object.insert(u"activated"_q, next);
	return Pack(object);
}

} // namespace

QByteArray HandleExternalControl(const QString &command) {
	if (!IsAppLaunched()) {
		return Error(u"application is not launched"_q);
	} else if (!AutomationEnabled()) {
		RequestEnableAutomation();
		return Error(u"本地自动化已关闭，请在 Chat 窗口中确认后启用"_q);
	} else if (command == u"automation-off"_q) { // TEMP test helper.
		Core::App().settings().writePref<bool>(kAutomationKey, false);
		auto object = QJsonObject();
		object.insert(u"ok"_q, true);
		return Pack(object);
	} else if (command == u"ping"_q) {
		auto object = QJsonObject();
		object.insert(u"ok"_q, true);
		object.insert(u"result"_q, u"pong"_q);
		return Pack(object);
	} else if (command == u"windows"_q) {
		return HandleWindows();
	} else if (command.startsWith(u"activate:"_q)) {
		return HandleActivate(command.mid(9).toInt());
	} else if (command == u"cycle"_q) {
		return HandleCycle();
	}
	return Error(u"unknown control command"_q);
}

} // namespace Core
