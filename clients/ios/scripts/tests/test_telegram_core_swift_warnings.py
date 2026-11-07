import ast
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPRODUCER = """\
import Foundation

final class Owner {
    var handler: (() -> Void)?

    func setup() {
        self.handler = {
            let nested: () -> Void = { [weak self] in
                self?.handler = nil
            }
            nested()
        }
    }
}
"""
IMPLICIT_CAPTURE_TARGETS = (
    "//submodules/TelegramUI/Components/Settings/PeerNameColorItem:PeerNameColorItem",
    "//submodules/TelegramUI/Components/PeerInfo/MessagePriceItem:MessagePriceItem",
    "//submodules/ItemListVenueItem:ItemListVenueItem",
    "//submodules/ItemListStickerPackItem:ItemListStickerPackItem",
    "//submodules/TelegramUI/Components/PeerInfo/PeerCopyProtectionInfoScreen:PeerCopyProtectionInfoScreen",
    "//submodules/ItemListPeerActionItem:ItemListPeerActionItem",
    "//submodules/ItemListAvatarAndNameInfoItem:ItemListAvatarAndNameInfoItem",
    "//submodules/ReactionSelectionNode:ReactionSelectionNode",
    "//submodules/TelegramUI/Components/Stars/StarsTransferScreen:StarsTransferScreen",
    "//submodules/BotPaymentsUI:BotPaymentsUI",
    "//submodules/TelegramUI/Components/Settings/QuickReactionSetupController:QuickReactionSetupController",
    "//submodules/ItemListPeerItem:ItemListPeerItem",
    "//submodules/TelegramUI/Components/Settings/ThemeCarouselItem:ThemeCarouselItem",
    "//submodules/TelegramUI/Components/Settings/ThemeSettingsThemeItem:ThemeSettingsThemeItem",
    "//submodules/TranslateUI:TranslateUI",
    "//submodules/ShareWithPeersScreen:ShareWithPeersScreen",
    "//submodules/AuthConfirmationScreen:AuthConfirmationScreen",
    "//submodules/HorizontalPeerItem:HorizontalPeerItem",
    "//submodules/TelegramUI/Components/Chat/ChatMessageInteractiveFileNode:ChatMessageInteractiveFileNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageCallBubbleContentNode:ChatMessageCallBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageFactCheckBubbleContentNode:ChatMessageFactCheckBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageTodoBubbleContentNode:ChatMessageTodoBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageReactionsFooterContentNode:ChatMessageReactionsFooterContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageCommentFooterContentNode:ChatMessageCommentFooterContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageTextBubbleContentNode:ChatMessageTextBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageContactBubbleContentNode:ChatMessageContactBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageMapBubbleContentNode:ChatMessageMapBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageRestrictedBubbleContentNode:ChatMessageRestrictedBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageBirthdateSuggestionContentNode:ChatMessageBirthdateSuggestionContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageUnsupportedBubbleContentNode:ChatMessageUnsupportedBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageWallpaperBubbleContentNode:ChatMessageWallpaperBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageGiftOfferBubbleContentNode:ChatMessageGiftOfferBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageDisableCopyProtectionBubbleContentNode:ChatMessageDisableCopyProtectionBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageInteractiveInstantVideoNode:ChatMessageInteractiveInstantVideoNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageGiveawayBubbleContentNode:ChatMessageGiveawayBubbleContentNode",
    "//submodules/TelegramUI/Components/Chat/ChatMessageGiftBubbleContentNode:ChatMessageGiftBubbleContentNode",
)


class TelegramCoreSwiftWarningTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("swiftc"), "Swift compiler is required")
    def test_swift_5_implicit_capture_warning_is_downgraded_for_strict_targets(self):
        strict_targets = (
            "submodules/TelegramCore",
            "submodules/SolidRoundedButtonNode",
            "submodules/InAppPurchaseManager",
            "submodules/TelegramVoip",
            "submodules/MediaPlayer",
            "submodules/AvatarNode",
            "submodules/Camera",
            "submodules/ItemListUI",
            "submodules/TelegramUI/Components/MediaEditor",
            "submodules/TelegramUpdateUI",
            "submodules/TelegramUI/Components/ItemListDatePickerItem",
            "submodules/ItemListAddressItem",
            "submodules/ChatListFilterSettingsHeaderItem",
            "submodules/TelegramUI/Components/AudioWaveformComponent",
            "submodules/TelegramUI/Components/Calls/CallScreen",
        )
        for target in strict_targets:
            with self.subTest(target=target):
                build_file = (ROOT / target / "BUILD").read_text(encoding="utf-8")
                copts_match = re.search(r"copts\s*=\s*(\[[\s\S]*?\])", build_file)
                self.assertIsNotNone(copts_match, f"{target} must declare Swift compiler options")
                copts = ast.literal_eval(copts_match.group(1))
                self.assertIn("-warnings-as-errors", copts)
                self.assertIn("-Wwarning", copts)
                self.assertIn("ImplicitStrongCapture", copts)

                result = subprocess.run(
                    ["swiftc", "-typecheck", "-swift-version", "5", *copts, "-"],
                    input=REPRODUCER,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("ImplicitStrongCapture", result.stderr)
                self.assertIn("warning:", result.stderr)

    def test_macos_bazel_build_downgrades_implicit_capture_warning_per_target(self):
        bazelrc = (ROOT / ".bazelrc").read_text(encoding="utf-8")
        for target in IMPLICIT_CAPTURE_TARGETS:
            with self.subTest(target=target):
                self.assertIn(
                    "build:macos --@build_bazel_rules_swift//swift:per_module_swiftcopt="
                    f"{target.replace('//', '@@//', 1)}=-Wwarning,ImplicitStrongCapture",
                    bazelrc,
                )
        self.assertNotIn("--@build_bazel_rules_swift//swift:copt=", bazelrc)

        result = subprocess.run(
            [
                "swiftc",
                "-typecheck",
                "-swift-version",
                "5",
                "-warnings-as-errors",
                "-Wwarning",
                "ImplicitStrongCapture",
                "-",
            ],
            input=REPRODUCER,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning:", result.stderr)
        self.assertIn("ImplicitStrongCapture", result.stderr)

    def test_animated_sticker_jpeg_type_uses_uniform_type_identifiers(self):
        source = (ROOT / "submodules/TelegramAnimatedStickerNode/Sources/AnimatedStickerUtils.swift").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("kUTTypeJPEG", source)
        self.assertIn("import UniformTypeIdentifiers", source)
        self.assertEqual(source.count("UTType.jpeg.identifier as CFString"), 2)

    def test_text_field_pasteboard_types_use_uniform_type_identifiers(self):
        source = (
            ROOT / "submodules/TelegramUI/Components/TextFieldComponent/Sources/TextFieldComponent.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("import UniformTypeIdentifiers", source)
        for deprecated_constant in ("kUTTypeRTF", "kUTTypePNG", "kUTTypeJPEG", "kUTTypeGIF"):
            with self.subTest(constant=deprecated_constant):
                self.assertNotIn(deprecated_constant, source)
        for type_name in ("rtf", "png", "jpeg", "gif"):
            with self.subTest(uniform_type=type_name):
                self.assertIn(f"UTType.{type_name}.identifier", source)

    def test_send_message_intent_uses_designated_initializer(self):
        source = (ROOT / "submodules/TelegramIntents/Sources/TelegramIntents.swift").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("INSendMessageIntent(recipients:", source)
        self.assertIn("outgoingMessageType: .outgoingMessageText", source)
        self.assertIn("attachments: nil", source)

    def test_pasteboard_and_media_types_use_uniform_type_identifiers(self):
        source_files = (
            "submodules/DrawingUI/Sources/DrawingTextEntityView.swift",
            "submodules/DrawingUI/Sources/DrawingScreen.swift",
            "submodules/AttachmentTextInputPanelNode/Sources/AttachmentTextInputPanelNode.swift",
            "submodules/SaveToCameraRoll/Sources/SaveToCameraRoll.swift",
            "submodules/TelegramUI/Sources/SpotlightContacts.swift",
            "submodules/TelegramUI/Sources/FetchCachedRepresentations.swift",
            "submodules/TelegramUI/Sources/ChatController.swift",
            "submodules/TelegramUI/Components/ShareExtensionContext/Sources/ShareExtensionContext.swift",
            "submodules/TelegramUI/Components/MediaEditorScreen/Sources/MediaEditorScreen.swift",
            "submodules/TelegramUI/Components/Chat/ChatTextInputPanelNode/Sources/ChatTextInputPanelNode.swift",
        )
        for relative_path in source_files:
            with self.subTest(source=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertTrue("import UniformTypeIdentifiers" in source, relative_path)
                self.assertFalse(re.search(r"\bkUTType[A-Za-z]+\b", source), relative_path)

    def test_graph_ui_keeps_legacy_button_api_warnings_nonfatal(self):
        build_file = (ROOT / "submodules/GraphUI/BUILD").read_text(encoding="utf-8")
        copts_match = re.search(r"copts\s*=\s*(\[[\s\S]*?\])", build_file)
        self.assertIsNotNone(copts_match)
        copts = ast.literal_eval(copts_match.group(1))
        self.assertIn("-warnings-as-errors", copts)
        self.assertIn("-Wwarning", copts)
        self.assertIn("DeprecatedDeclaration", copts)

    def test_location_authorization_uses_instance_status_api(self):
        source_files = (
            "submodules/DeviceAccess/Sources/DeviceAccess.swift",
            "submodules/DeviceAccess/Sources/LocationManager.swift",
            "submodules/LocationUI/Sources/LocationPickerControllerNode.swift",
            "submodules/WebUI/Sources/WebAppController.swift",
        )
        for relative_path in source_files:
            with self.subTest(source=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("CLLocationManager.authorizationStatus()", source, relative_path)
        device_access = (ROOT / source_files[0]).read_text(encoding="utf-8")
        self.assertNotIn("let locationManager = CLLocationManager()", device_access)
        self.assertIn("let systemLocationManager = CLLocationManager()", device_access)

    def test_legacy_application_windows_use_connected_scenes(self):
        source = (
            ROOT / "submodules/LegacyUI/Sources/TelegramInitializeLegacyComponents.swift"
        ).read_text(encoding="utf-8")
        self.assertNotIn("legacyComponentsApplication?.windows", source)
        self.assertIn("connectedScenes", source)
        self.assertIn("UIWindowScene", source)


if __name__ == "__main__":
    unittest.main()
