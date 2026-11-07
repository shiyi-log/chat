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

    def test_auth_confirmation_account_menu_uses_explicit_weak_outer_capture(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/AuthConfirmationScreen/Sources/AuthConfirmationScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("|> map { [weak self] primary, other -> [ContextMenuItem] in", source)

    def test_share_with_peers_proceed_callback_uses_explicit_weak_captures(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/ShareWithPeersScreen/Sources/ShareWithPeersScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("let proceed = { [weak controller, weak component] in", source)
        self.assertIn("let complete = { [weak controller, weak component] in", source)

    def test_chat_file_layout_uses_explicit_weak_outer_capture(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageFileBubbleContentNode/Sources/ChatMessageFileBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "return { [weak self] item, layoutConstants, preparePosition, selection, constrainedSize, _ in",
            source,
        )

    def test_chat_instant_video_layout_uses_explicit_weak_outer_capture(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageInstantVideoBubbleContentNode/Sources/ChatMessageInstantVideoBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "return { [weak self] item, layoutConstants, preparePosition, selection, constrainedSize, avatarInset in",
            source,
        )

    def test_chat_attached_content_layout_explicitly_captures_controller_interaction(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageAttachedContentNode/Sources/ChatMessageAttachedContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip() for line in source.splitlines() if "return (maxWidth, {" in line
        )
        self.assertEqual(
            layout_signature,
            "return (maxWidth, { [controllerInteraction] constrainedSize, position in",
        )

    def test_chat_media_layout_explicitly_captures_node_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageMediaBubbleContentNode/Sources/ChatMessageMediaBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith("return {")
            and "layoutConstants, preparePosition, selection, constrainedSize, _ in" in line
        )
        self.assertEqual(
            layout_signature,
            "return { [self] item, layoutConstants, preparePosition, selection, constrainedSize, _ in",
        )

    def test_chat_game_layout_explicitly_captures_node_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageGameBubbleContentNode/Sources/ChatMessageGameBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip()
            for line in source.splitlines()
            if "layoutConstants, preparePosition, _, constrainedSize, _ in" in line
        )
        self.assertEqual(
            layout_signature,
            "return { [self] item, layoutConstants, preparePosition, _, constrainedSize, _ in",
        )

    def test_webpage_layout_explicitly_captures_content_node_for_weak_animation(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageWebpageBubbleContentNode/Sources/ChatMessageWebpageBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip()
            for line in source.splitlines()
            if "layoutConstants, preparePosition, _, constrainedSize, _ in" in line
        )
        self.assertEqual(
            layout_signature,
            "return { [self, contentNode = self.contentNode] item, layoutConstants, preparePosition, _, constrainedSize, _ in",
        )
        self.assertTrue(
            any("return (size, { [weak self] animation, synchronousLoads, applyInfo in" in line for line in source.splitlines()),
            "webpage apply closure should remain weak",
        )
        self.assertTrue(
            any("completion: { [weak contentNode] _ in" in line for line in source.splitlines()),
            "webpage removal animation should remain weak",
        )

    def test_chat_poll_layouts_explicitly_capture_nodes_for_weak_apply(self):
        expected_signatures = {
            "ChatMessagePollBubbleContentNode/Sources/ChatMessagePollBubbleContentNode.swift":
                "return { [self] item, layoutConstants, _, _, _, _ in",
            "ChatMessagePollBubbleContentNode/Sources/ChatMessageQuizAnswerBubbleContentNode.swift":
                "return { [self] item, layoutConstants, preparePosition, _, constrainedSize, _ in",
        }
        for relative_path, expected_signature in expected_signatures.items():
            source = (
                ROOT
                / "submodules/TelegramUI/Components/Chat"
                / relative_path
            ).read_text(encoding="utf-8")
            with self.subTest(file=relative_path):
                self.assertTrue(
                    any(expected_signature in line for line in source.splitlines()),
                    f"{relative_path} should explicitly capture its outer node",
                )

    def test_joined_channel_callbacks_explicitly_capture_outer_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageJoinedChannelBubbleContentNode/Sources/ChatMessageJoinedChannelBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        source_lines = source.splitlines()
        self.assertTrue(
            any("return { [self] item, layoutConstants, _, _, constrainedSize, _ in" in line for line in source_lines),
            "joined-channel layout should explicitly capture its node before weak apply",
        )
        self.assertTrue(
            any("action: { [self] peer in" in line for line in source_lines),
            "recommended-channel action should explicitly capture its node before weak undo action",
        )
        self.assertTrue(
            any("action: { [weak self] action in" in line for line in source_lines),
            "premium undo action should remain weak",
        )

    def test_event_log_layout_explicitly_captures_node_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageEventLogPreviousLinkContentNode/Sources/ChatMessageEventLogPreviousLinkContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip()
            for line in source.splitlines()
            if "layoutConstants, preparePosition, _, constrainedSize, _ in" in line
        )
        self.assertEqual(
            layout_signature,
            "return { [self] item, layoutConstants, preparePosition, _, constrainedSize, _ in",
        )

    def test_event_log_previous_message_layout_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageEventLogPreviousMessageContentNode/Sources/ChatMessageEventLogPreviousMessageContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip()
            for line in source.splitlines()
            if "layoutConstants, preparePosition, _, constrainedSize, _ in" in line
        )
        self.assertEqual(
            layout_signature,
            "return { [self] item, layoutConstants, preparePosition, _, constrainedSize, _ in",
        )

    def test_event_log_description_layout_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageEventLogPreviousDescriptionContentNode/Sources/ChatMessageEventLogPreviousDescriptionContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip()
            for line in source.splitlines()
            if "layoutConstants, preparePosition, _, constrainedSize, _ in" in line
        )
        self.assertEqual(
            layout_signature,
            "return { [self] item, layoutConstants, preparePosition, _, constrainedSize, _ in",
        )

    def test_invoice_layout_explicitly_captures_node_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageInvoiceBubbleContentNode/Sources/ChatMessageInvoiceBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        layout_signature = next(
            line.strip()
            for line in source.splitlines()
            if "layoutConstants, preparePosition, _, constrainedSize, _ in" in line
        )
        self.assertEqual(
            layout_signature,
            "return { [self] item, layoutConstants, preparePosition, _, constrainedSize, _ in",
        )

    def test_storage_usage_menu_explicitly_captures_source_view(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/StorageUsageScreen/Sources/StorageUsageScreen.swift"
        ).read_text(encoding="utf-8")
        callback_signature = next(
            line.strip()
            for line in source.splitlines()
            if "cacheSettings, peerExceptions in" in line
        )
        self.assertEqual(
            callback_signature,
            "|> deliverOnMainQueue).start(next: { [sourceView] cacheSettings, peerExceptions in",
        )
        self.assertIn("contextController.dismissed = { [weak sourceView] in", source)

    def test_peer_info_item_layouts_explicitly_capture_outer_nodes(self):
        expected_signatures = {
            "ItemListReactionItem.swift": "return { [self] item, params, neighbors in",
            "ItemListSecretChatKeyItem.swift": "return { [self] item, params, neighbors in",
            "ChannelDiscussionGroupSetupHeaderItem.swift": "return { [self] item, params, neighbors in",
            "PeerAutoremoveTimeoutItem.swift": "return { [self] item, params, neighbors in",
            "ChatSlowmodeItem.swift": "return { [self] item, params, neighbors in",
            "ChatUnrestrictBoostersItem.swift": "return { [self] item, params, neighbors in",
            "UserInfoEditingPhoneActionItem.swift": "return { [self] item, params, neighbors in",
            "UserInfoEditingPhoneItem.swift": "return { [self] item, params, neighbors in",
        }
        for filename, expected_signature in expected_signatures.items():
            source = (ROOT / "submodules/PeerInfoUI/Sources" / filename).read_text(encoding="utf-8")
            with self.subTest(file=filename):
                self.assertTrue(
                    any(expected_signature in line for line in source.splitlines()),
                    f"{filename} should explicitly capture its outer layout node",
                )

    def test_contact_creation_menu_explicitly_captures_parent_controller(self):
        source = (ROOT / "submodules/PeerInfoUI/Sources/DeviceContactInfoController.swift").read_text(encoding="utf-8")
        self.assertTrue(
            any("action: { [parentController] _, f in" in line for line in source.splitlines()),
            "contact creation action should explicitly capture its controller",
        )
        self.assertTrue(
            any("present: { [weak parentController] c, a in" in line for line in source.splitlines()),
            "nested presentation callback should remain weak",
        )

    def test_premium_layout_helpers_weakly_capture_component_state(self):
        source = (ROOT / "submodules/PremiumUI/Sources/PremiumIntroScreen.swift").read_text(encoding="utf-8")
        for closure_name in ("layoutPerks", "layoutBusinessPerks", "layoutMoreBusinessPerks", "layoutAdsSettings"):
            with self.subTest(closure=closure_name):
                self.assertIn(f"let {closure_name} = {{ [weak state] in", source)

    def test_premium_resolved_url_callback_weakly_captures_controller(self):
        source = (ROOT / "submodules/PremiumUI/Sources/PremiumIntroScreen.swift").read_text(encoding="utf-8")
        self.assertIn("|> deliverOnMainQueue).start(next: { [weak controller] resolvedUrl in", source)

    def test_premium_item_layouts_and_actions_use_explicit_weak_captures(self):
        subscriptions = (ROOT / "submodules/PremiumUI/Sources/SubscriptionsCountItem.swift").read_text(encoding="utf-8")
        self.assertIn("return { [weak self] item, params, neighbors in", subscriptions)

        increase_limit = (ROOT / "submodules/PremiumUI/Sources/IncreaseLimitHeaderItem.swift").read_text(encoding="utf-8")
        self.assertIn("return { [weak self] item, params, neighbors in", increase_limit)

        boost_levels = (ROOT / "submodules/PremiumUI/Sources/PremiumBoostLevelsScreen.swift").read_text(encoding="utf-8")
        self.assertIn("|> deliverOnMainQueue).start(next: { [weak controller, weak self] peer in", boost_levels)

        gift_screen = (ROOT / "submodules/PremiumUI/Sources/PremiumGiftScreen.swift").read_text(encoding="utf-8")
        self.assertIn("|> deliverOnMainQueue).start(next: { [weak controller] resolvedUrl in", gift_screen)

        gift_option = (ROOT / "submodules/PremiumUI/Sources/GiftOptionItem.swift").read_text(encoding="utf-8")
        self.assertIn("return { [weak self] item, params, neighbors in", gift_option)

    def test_translation_menu_signal_does_not_implicitly_retain_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/TranslateHeaderPanelComponent/Sources/ChatTranslationPanelNode.swift"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"\|> map \{ \[weak self\] sharedData -> ContextController\.Items in",
        )

    def test_featured_sticker_highlight_delay_weakly_captures_node(self):
        source = (
            ROOT
            / "submodules/FeaturedStickersScreen/Sources/StickerPaneSearchGlobaltem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("Queue.mainQueue().after(1.5) { [weak highlightNode] in", source)
        self.assertIn("highlightNode?.layer.animateAlpha", source)

    def test_group_sticker_pack_layout_weakly_captures_outer_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/GroupStickerPackSetupController/Sources/GroupStickerPackCurrentItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "return { [weak self] item, params, neighbors in",
            source,
        )

    def test_drawing_font_button_uses_configuration_content_insets(self):
        source = (ROOT / "submodules/DrawingUI/Sources/TextSettingsComponent.swift").read_text(encoding="utf-8")
        self.assertIn("configuration.contentInsets = NSDirectionalEdgeInsets(", source)
        self.assertIn("self.button.configuration = configuration", source)

    def test_drawing_snapshot_fade_weakly_captures_snapshot_view(self):
        source = (ROOT / "submodules/DrawingUI/Sources/DrawingView.swift").read_text(encoding="utf-8")
        self.assertIn("Queue.mainQueue().justDispatch { [weak snapshotView] in", source)
        self.assertIn("snapshotView?.layer.animateAlpha", source)

    def test_legacy_attachment_processing_weakly_captures_owner_objects(self):
        source = (ROOT / "submodules/LegacyMediaPickerUI/Sources/LegacyAttachmentMenu.swift").read_text(encoding="utf-8")
        self.assertIn(
            "let process: (Bool) -> Void = { [weak controller, weak carouselItem] convert in",
            source,
        )

    def test_legacy_paint_async_load_weakly_captures_entity(self):
        source = (ROOT / "submodules/LegacyMediaPickerUI/Sources/LegacyPaintStickersContext.swift").read_text(encoding="utf-8")
        self.assertIn("self.queue.async { [weak self] in", source)
        self.assertIn("guard let self else", source)

    def test_legacy_document_picker_uses_modern_uniform_type_api(self):
        source = (ROOT / "submodules/LegacyMediaPickerUI/Sources/LegacyICloudFilePicker.swift").read_text(encoding="utf-8")
        self.assertIn("import UniformTypeIdentifiers", source)
        self.assertIn("forOpeningContentTypes:", source)
        self.assertIn("forExporting:", source)
        self.assertNotIn("UIDocumentPickerMode", source)
        self.assertNotIn("documentTypes: documentTypes, in:", source)

    def test_avatar_editor_frame_callback_weakly_captures_controller(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/AvatarEditorScreen/Sources/AvatarEditorScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("completion: { [weak controller] result in", source)
        self.assertIn("guard let controller, let item = result.item else", source)
        self.assertIn("Queue.mainQueue().async { [weak controller] in", source)

    def test_qr_code_navigation_callback_weakly_captures_navigation_controller(self):
        source = (ROOT / "submodules/QrCodeUI/Sources/QrCodeScanScreen.swift").read_text(encoding="utf-8")
        self.assertIn("openPeer: { [weak self, weak navigationController] peer, navigation in", source)
        self.assertIn(
            "guard let strongSelf = self, let navigationController = navigationController else",
            source,
        )

    def test_video_message_camera_reads_orientation_from_window_scene(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/VideoMessageCameraScreen/Sources/VideoMessageCameraScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("self.view.window?.windowScene?.interfaceOrientation", source)
        self.assertNotIn("UIApplication.shared.windows", source)

    def test_auth_code_keyboard_snapshot_fade_weakly_captures_view(self):
        source = (
            ROOT
            / "submodules/AuthorizationUI/Sources/AuthorizationSequenceCodeEntryController.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "Queue.mainQueue().after(local ? 0.8 : 0.7, { [weak snapshotView] in",
            source,
        )
        self.assertIn("snapshotView?.layer.animateAlpha", source)

    def test_gift_preview_layout_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Gifts/GiftSetupScreen/Sources/ChatGiftPreviewItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("return { [self] item, params, neighbors in", source)

    def test_gift_purchase_callback_explicitly_captures_stars_context(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Gifts/GiftSetupScreen/Sources/GiftSetupScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "startStandalone(next: { [weak self, starsContext] options in",
            source,
        )

    def test_gift_media_node_delay_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Gifts/GiftSetupScreen/Sources/GiftSetupScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("Queue.mainQueue().after(0.3) { [inputMediaNode] in", source)

    def test_import_sticker_pack_delay_explicitly_captures_controller(self):
        source = (
            ROOT
            / "submodules/ImportStickerPackUI/Sources/ImportStickerPackController.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("Queue.mainQueue().after(0.1) { [self] in", source)

    def test_chat_document_gallery_disables_javascript_with_webpage_preferences(self):
        source = (
            ROOT
            / "submodules/GalleryUI/Sources/Items/ChatDocumentGalleryItem.swift"
        ).read_text(encoding="utf-8")
        lines = source.splitlines()
        self.assertIn(
            "            configuration.defaultWebpagePreferences.allowsContentJavaScript = false",
            lines,
        )
        self.assertNotIn("javaScriptEnabled", source)

    def test_universal_video_expansion_explicitly_captures_context(self):
        source = (
            ROOT
            / "submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("            expandImpl = { [weak overlayNode, context] in", source.splitlines())

    def test_universal_video_save_action_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "                                let addItem: (Int?, FileMediaReference) -> Void = { [self] quality, qualityFile in",
            source.splitlines(),
        )

    def test_story_mention_layout_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageStoryMentionContentNode/Sources/ChatMessageStoryMentionContentNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "        return { [self] item, layoutConstants, _, _, _, _ in",
            source.splitlines(),
        )

    def test_qr_code_delayed_actions_explicitly_capture_owners(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatQrCodeScreen/Sources/ChatQrCodeScreen.swift"
        ).read_text(encoding="utf-8")
        lines = source.splitlines()
        self.assertIn("            Queue.mainQueue().after(0.1) { [self, animatedStickerNode] in", lines)
        self.assertIn("            Queue.mainQueue().after(themeCrossfadeDelay) { [self] in", lines)

    def test_action_bubble_layout_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageActionBubbleContentNode/Sources/ChatMessageActionBubbleContentNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "        return { [self] item, layoutConstants, _, _, _, _ in",
            source.splitlines(),
        )

    def test_wallpaper_gallery_delay_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Settings/WallpaperGalleryScreen/Sources/WallpaperGalleryItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("            Queue.mainQueue().after(0.1) { [self] in", source.splitlines())

    def test_passport_updated_values_explicitly_captures_controller(self):
        source = (
            ROOT
            / "submodules/PassportUI/Sources/SecureIdAuthControllerNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "        let updatedValues: (SecureIdValueKey) -> ([SecureIdValueWithContext]) -> Void = { [self] valueKey in",
            source.splitlines(),
        )

    def test_profile_photo_suggestion_layout_explicitly_captures_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageProfilePhotoSuggestionContentNode/Sources/ChatMessageProfilePhotoSuggestionContentNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "        return { [self] item, layoutConstants, _, _, _, _ in",
            source.splitlines(),
        )

    def test_invite_link_layouts_explicitly_capture_nodes(self):
        expected_lines = {
            "submodules/InviteLinksUI/Sources/InviteLinkInviteHeaderItem.swift":
                "        return { [self] item, params, neighbors in",
            "submodules/InviteLinksUI/Sources/InviteLinkHeaderItem.swift":
                "        return { [self] item, params, neighbors in",
            "submodules/InviteLinksUI/Sources/InviteLinkInviteManageItem.swift":
                "        return { [self] item, params, neighbors in",
            "submodules/InviteLinksUI/Sources/ItemListInviteLinkDateLimitItem.swift":
                "        return { [self] item, params, neighbors in",
            "submodules/InviteLinksUI/Sources/ItemListInviteLinkItem.swift":
                "        return { [self] item, params, neighbors, firstWithHeader, last in",
            "submodules/InviteLinksUI/Sources/ItemListFolderInviteLinkItem.swift":
                "        return { [self] item, params, neighbors in",
            "submodules/InviteLinksUI/Sources/ItemListFolderInviteLinkListItem.swift":
                "        return { [self] item, params, neighbors, firstWithHeader, last in",
            "submodules/InviteLinksUI/Sources/ItemListInviteLinkUsageLimitItem.swift":
                "        return { [self] item, params, neighbors in",
            "submodules/InviteLinksUI/Sources/ItemListInviteRequestItem.swift":
                "        return { [self] item, params, neighbors, firstWithHeader, last in",
            "submodules/InviteLinksUI/Sources/AdditionalLinkItem.swift":
                "        return { [self] item, params, neighbors, firstWithHeader, last in",
            "submodules/InviteLinksUI/Sources/ItemListPermanentInviteLinkItem.swift":
                "        return { [self] item, params, neighbors in",
        }
        for relative_path, expected_line in expected_lines.items():
            with self.subTest(path=relative_path):
                lines = (ROOT / relative_path).read_text(encoding="utf-8").splitlines()
                self.assertTrue(expected_line in lines, f"{relative_path} has an implicit outer capture")

    def test_callkit_uses_current_intent_and_provider_apis(self):
        source = (ROOT / "submodules/TelegramCallsUI/Sources/CallKitIntegration.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "INStartCallIntent(callRecordFilter: nil, callRecordToCallBack: nil, audioRoute: .unknown, destinationType: .normal, contacts: [contact], callCapability: .audioCall)" in source,
            "CallKit should use the nondeprecated INStartCallIntent initializer",
        )
        self.assertTrue(
            "let providerConfiguration = CXProviderConfiguration()" in source,
            "CallKit provider configuration should use its current initializer",
        )
        self.assertFalse("recordTypeForRedialing:" in source, "the deprecated call record argument remains")
        self.assertFalse("CXProviderConfiguration(localizedName:" in source, "the deprecated provider initializer remains")

    def test_media_stream_pip_uses_the_active_window_scene(self):
        source = (ROOT / "submodules/TelegramCallsUI/Sources/Components/MediaStreamVideoComponent.swift").read_text(encoding="utf-8")
        self.assertTrue("self.window?.windowScene?.windows.first" in source, "PiP should use its window scene")
        self.assertFalse("UIApplication.shared.windows" in source, "deprecated app-wide window access remains")

    def test_voice_chat_callbacks_explicitly_capture_outer_owners(self):
        expected_lines = {
            "submodules/TelegramCallsUI/Sources/VoiceChatParticipantItem.swift": [
                ("        return { [self] size, text, expanded in", 1),
                ("        return { [self] item, params, first, last in", 1),
            ],
            "submodules/TelegramCallsUI/Sources/VoiceChatActionItem.swift": [
                ("        return { [self] item, params, first, last in", 1),
            ],
            "submodules/TelegramCallsUI/Sources/VoiceChatFullscreenParticipantItem.swift": [
                ("        return { [self] item, params, first, last in", 1),
            ],
            "submodules/TelegramCallsUI/Sources/Components/MessageItemComponent.swift": [
                ("                    Queue.mainQueue().justDispatch { [self] in", 1),
            ],
            "submodules/TelegramCallsUI/Sources/VideoChatScreen.swift": [
                ("                            Queue.mainQueue().after(0.2) { [inputMediaNode] in", 2),
            ],
            "submodules/TelegramCallsUI/Sources/VoiceChatTileGridNode.swift": [
                ("        return { [self] item, params in", 1),
            ],
            "submodules/TelegramCallsUI/Sources/GroupVideoNode.swift": [
                ("                Queue.mainQueue().after(0.3) { [snapshotView] in", 1),
            ],
        }
        for relative_path, expectations in expected_lines.items():
            with self.subTest(path=relative_path):
                lines = (ROOT / relative_path).read_text(encoding="utf-8").splitlines()
                for expected_line, expected_count in expectations:
                    self.assertEqual(
                        lines.count(expected_line),
                        expected_count,
                        f"{relative_path} should explicitly capture its outer owner",
                    )

    def test_group_call_peer_lookup_explicitly_captures_controller(self):
        source = (ROOT / "submodules/TelegramBaseController/Sources/TelegramBaseController.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "self.context.joinGroupCall(peerId: peerId, invite: invite, requestJoinAsPeerId: { [self] completion in" in source,
            "group call peer lookup should explicitly retain its controller callback owner",
        )

    def test_call_list_hole_layout_explicitly_captures_node(self):
        source = (ROOT / "submodules/CallListUI/Sources/CallListHoleItem.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "        return { [self] item, params, first, last in" in source,
            "call list hole layout should explicitly retain its node",
        )

    def test_attachment_panel_callbacks_explicitly_capture_outer_owners(self):
        source = (ROOT / "submodules/AttachmentUI/Sources/AttachmentPanel.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "startStandalone(next: { [weak self, textInputPanelNode] peerView, effectItems, availableMessageEffects, hasPremium in" in source,
            "send-message option callbacks should make their panel-node capture explicit",
        )
        self.assertTrue(
            "        let action = { [self, inputNodeSnapshotView] in" in source,
            "attachment transition actions should make their owner captures explicit",
        )

    def test_group_call_context_signal_explicitly_captures_context(self):
        source = (ROOT / "submodules/TelegramUI/Components/GlobalControlPanelsContext/Sources/GlobalControlPanelsContext.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "|> mapToSignal { [context] activeCall, peer -> Signal<AccountGroupCallContextImpl.GroupCallPanelData?, NoError> in" in source,
            "group call panel signal should explicitly capture its outer context",
        )

    def test_chat_theme_sticker_delay_explicitly_captures_owners(self):
        source = (ROOT / "submodules/TelegramUI/Components/ChatThemeScreen/Sources/ChatThemeScreen.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "            Queue.mainQueue().after(0.1) { [self, animatedStickerNode] in" in source,
            "chat theme sticker delay should explicitly retain its node and owner",
        )

    def test_media_picker_callbacks_explicitly_capture_outer_values(self):
        expected_lines = {
            "submodules/MediaPickerUI/Sources/MediaGroupsAlbumGridItem.swift":
                "            return (nodeLayout, { [weak self, item] in",
            "submodules/MediaPickerUI/Sources/MediaGroupsAlbumItem.swift":
                "        return { [self] item, params, first, last in",
            "submodules/MediaPickerUI/Sources/LegacyMediaPickerGallery.swift":
                "                |> deliverOnMainQueue).start(next: { [model] sendWhenOnlineAvailable in",
            "submodules/MediaPickerUI/Sources/MediaPickerScreen.swift":
                "    controller.requestController = { [selectionContext] _, present in",
        }
        for relative_path, expected_line in expected_lines.items():
            with self.subTest(path=relative_path):
                lines = (ROOT / relative_path).read_text(encoding="utf-8").splitlines()
                self.assertTrue(expected_line in lines, f"{relative_path} has an implicit nested capture")

    def test_phone_input_layout_explicitly_captures_node(self):
        source = (ROOT / "submodules/TelegramUI/Components/Contacts/NewContactScreen/Sources/PhoneInputItem.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "        return { [self] item, params, neighbors in" in source,
            "phone input layout should explicitly retain its node",
        )

    def test_media_editor_nested_callbacks_explicitly_capture_outer_owners(self):
        story_completion = (
            ROOT
            / "submodules/TelegramUI/Components/MediaEditorScreen/Sources/MediaEditorStoryCompletion.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("dispatchGroup.notify(queue: .main) { [self] in", story_completion)
        self.assertIn("self.completion(orderedResults, { [weak self] finished in", story_completion)

        media_editor = (
            ROOT
            / "submodules/TelegramUI/Components/MediaEditorScreen/Sources/MediaEditorScreen.swift"
        ).read_text(encoding="utf-8")
        for expected in (
            "Queue.mainQueue().after(0.2) { [inputMediaNode] in",
            "completion: { [weak inputMediaNode] _ in",
            "Queue.concurrentDefaultQueue().after(0.5, { [self] in",
            "} |> afterNext { [weak self] _ in",
            "Queue.mainQueue().after(0.3) { [self] in",
            "replaceImpl = { [weak self, weak demoController] c in",
        ):
            with self.subTest(capture=expected):
                self.assertIn(expected, media_editor)

    def test_chat_list_notice_layout_weakly_captures_outer_node(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/ChatList/ChatListHeaderNoticeComponent/Sources/ChatListNoticeItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("return { [self] item, params, last in", source)
        self.assertIn("return (layout, { [weak self] in", source)

    def test_gift_view_nested_callbacks_explicitly_capture_outer_values(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Gifts/GiftViewScreen/Sources/GiftViewScreen.swift"
        ).read_text(encoding="utf-8")
        expected_lines = (
            "let action = { [navigationController] in",
            "Queue.mainQueue().after(0.5) { [navigationController] in",
            "startStandalone(next: { [weak self, starsContext] options in",
            "action: { [weak self, controller] c, f in",
            "Queue.mainQueue().after(0.5, { [navigationController] in",
            "let proceed: (Int64?) -> Void = { [weak self, starsContext] formId in",
            "let proceed: () -> Void = { [weak self, weak starsContext, controller] in",
            "startStandalone(next: { [weak self, weak controller, starsContext] options in",
            "start(next: { [weak self, controller] peer in",
        )
        for expected in expected_lines:
            with self.subTest(capture=expected):
                self.assertTrue(expected in source, f"missing explicit outer capture: {expected}")
        self.assertEqual(
            source.count("Queue.mainQueue().after(0.5, { [navigationController] in"),
            2,
        )
        self.assertIn("completion: { [weak self, weak starsContext] stars in", source)
        self.assertIn("|> deliverOnMainQueue).start(next: { [weak self, weak controller, weak starsContext] result in", source)

    def test_story_send_callbacks_explicitly_capture_outer_owners(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryItemSetContainerViewSendMessage.swift"
        ).read_text(encoding="utf-8")
        expected = (
            "Queue.mainQueue().after(0.3) { [inputMediaNode] in",
            "self.presentPaidMessageAlertIfNeeded(view: view, completion: { [weak self, view] in",
            ".start(next: { [self, weak view] peer in",
            "send: { [weak self, weak view] videoController, message in",
            "displaySlowmodeTooltip: { [weak self] view, rect in",
            "presentSchedulePicker: { [weak self, weak view] done in",
            "Task { @MainActor [self, weak view] in",
            "send: { [self, weak view] mediaReferences, _, _, _ in",
            ".start(next: { [weak parentController, self, view] packs in",
            "let action = { [controller, self, view] in",
        )
        for capture in expected:
            with self.subTest(capture=capture):
                self.assertTrue(capture in source, f"missing explicit outer capture: {capture}")
        self.assertIn("completion: { [weak inputMediaNode] _ in", source)

    def test_story_interaction_callbacks_explicitly_capture_outer_owners(self):
        interaction = (
            ROOT
            / "submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryInteractionGuideComponent.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("Queue.mainQueue().justDispatch { [self, view] in", interaction)
        self.assertIn("let completionBlock = { [weak self] in", interaction)
        self.assertIn("view.playOnce(force: true, completion: { [weak view] in", interaction)

        reaction = (
            ROOT
            / "submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/LiveChatReactionStreamView.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("Task { [self] in", reaction)
        self.assertIn("completion: { [weak self] image in", reaction)

    def test_camera_recording_nested_callback_explicitly_captures_outer_owner(self):
        source = (ROOT / "submodules/TelegramUI/Components/CameraScreen/Sources/CameraScreen.swift").read_text(encoding="utf-8")
        self.assertIn("let startRecording = { [self] in", source)
        self.assertIn("|> deliverOnMainQueue).start(next: { [weak self] recordingData in", source)

    def test_interactive_video_layout_explicitly_captures_weak_store_context(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageInteractiveMediaNode/Sources/ChatMessageInteractiveMediaNode.swift"
        ).read_text(encoding="utf-8")
        self.assertTrue(
            "return (nativeSize, maxWidth, { [context] constrainedSize, automaticPlayback, wideLayout, corners in" in source,
            "interactive video layout should explicitly capture the context used weakly by its nested store callback",
        )
        self.assertIn("storeAfterDownload: { [weak context] in", source)

    def test_contact_list_layouts_explicitly_capture_outer_nodes(self):
        action_item = (ROOT / "submodules/ContactListUI/Sources/ContactListActionItem.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "return { [self] item, params, firstWithHeader, last in" in action_item,
            "contact action layout should explicitly retain its node outside the weak apply closure",
        )
        self.assertIn("return (layout, { [weak self] in", action_item)

        permission_item = (ROOT / "submodules/ContactListUI/Sources/LimitedPermissionItem.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "return { [self] item, params, neighbors in" in permission_item,
            "limited permission layout should explicitly retain its node outside the weak apply closure",
        )
        self.assertIn("return (layout, { [weak self] in", permission_item)

    def test_gallery_mapping_explicitly_captures_weak_navigation_controller(self):
        source = (ROOT / "submodules/GalleryData/Sources/GalleryData.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "|> map { [navigationController] startState in" in source,
            "gallery mapping should explicitly capture navigation controller for its weak nested callback",
        )
        self.assertIn("replaceRootController: { [weak navigationController] controller, ready in", source)

    def test_gift_store_balance_menu_explicitly_captures_outer_owner(self):
        source = (ROOT / "submodules/TelegramUI/Components/Gifts/GiftStoreScreen/Sources/GiftStoreScreen.swift").read_text(encoding="utf-8")
        self.assertTrue(
            "|> map { [self] starsState, tonState -> [ContextMenuItem] in" in source,
            "balance menu mapping should explicitly capture its owner outside weak menu actions",
        )
        self.assertIn("action: { [weak self] _, f in", source)

    def test_stars_send_undo_delay_explicitly_captures_controller(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Stars/StarsTransactionsScreen/Sources/StarsTransactionsScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertTrue(
            any("Queue.mainQueue().after(2.0) { [self] in" in line for line in source.splitlines()),
            "undo overlay delay should explicitly capture its controller before the weak action",
        )
        self.assertTrue(
            any("action: { [weak self] action in" in line for line in source.splitlines()),
            "undo action should remain weak",
        )

    def test_compose_poll_callbacks_explicitly_capture_outer_owners(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/ComposePollScreen/Sources/ComposePollScreen.swift"
        ).read_text(encoding="utf-8")
        source_lines = source.splitlines()
        self.assertTrue(
            any("let processPollOptionItem: (Int) -> Void = { [self] i in" in line for line in source_lines),
            "poll-option factory should explicitly capture its owner before weak callbacks",
        )
        self.assertTrue(
            any("Queue.mainQueue().after(0.3) { [inputMediaNode] in" in line for line in source_lines),
            "input-node removal delay should explicitly capture the node before its weak animation callback",
        )
        self.assertTrue(
            any("completion: { [weak inputMediaNode] _ in" in line for line in source_lines),
            "input-node removal animation should remain weak",
        )

    def test_compose_todo_callbacks_explicitly_capture_outer_owners(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/ComposeTodoScreen/Sources/ComposeTodoScreen.swift"
        ).read_text(encoding="utf-8")
        source_lines = source.splitlines()
        self.assertTrue(
            any("let processTodoItemItem: (Int) -> Void = { [self] i in" in line for line in source_lines),
            "todo-item factory should explicitly capture its owner before weak callbacks",
        )
        self.assertTrue(
            any("Queue.mainQueue().after(0.3) { [inputMediaNode] in" in line for line in source_lines),
            "input-node removal delay should explicitly capture the node before its weak animation callback",
        )
        self.assertTrue(
            any("completion: { [weak inputMediaNode] _ in" in line for line in source_lines),
            "input-node removal animation should remain weak",
        )

    def test_chat_list_item_layouts_explicitly_capture_outer_nodes(self):
        expected_signatures = {
            "ChatListFilterPresetCategoryItem.swift": (
                "return { [self] item, params, neighbors, headerAtTop in",
                1,
            ),
            "ChatListFilterPresetListItem.swift": (
                "return { [self] item, params, neighbors in",
                1,
            ),
            "ChatListFilterPresetListSuggestedItem.swift": (
                "return { [self] item, params, neighbors in",
                1,
            ),
            "ChatListFilterTagSectionHeaderItem.swift": (
                "return { [self] item, params, neighbors in",
                1,
            ),
            "Node/ChatListHoleItem.swift": (
                "return { [self] item, params, first, last in",
                1,
            ),
            "Node/ChatListArchiveInfoItem.swift": (
                "return { [self] item, params, last in",
                1,
            ),
            "Node/ChatListEmptyHeaderItem.swift": (
                "return { [self] item, params, last in",
                1,
            ),
            "Node/ChatListEmptyInfoItem.swift": (
                "return { [self] item, params, last in",
                2,
            ),
            "Node/ChatListItem.swift": (
                "return { [self] item, params, first, last, firstWithHeader, nextIsPinned, nextHasActiveRevealControls in",
                1,
            ),
        }
        for filename, (signature, expected_count) in expected_signatures.items():
            lines = (ROOT / "submodules/ChatListUI/Sources" / filename).read_text(encoding="utf-8").splitlines()
            with self.subTest(file=filename):
                self.assertEqual(
                    sum(line.strip() == signature for line in lines),
                    expected_count,
                    f"{filename} should explicitly capture its outer layout node",
                )

    def test_chat_list_nested_callbacks_explicitly_capture_outer_values(self):
        expected_captures = {
            "ChatListControllerLeaveChatConfirmation.swift": (
                "Task { @MainActor [self] in",
                "action: { [weak self] in",
            ),
            "ChatListControllerNode.swift": (
                "return { [weak self, weak placeholderNode, searchDisplayController] in",
                "completion: { [weak self, weak searchDisplayController] in",
            ),
            "ChatListFilterPresetController.swift": (
                "Queue.mainQueue().after(0.3) { [inputMediaNode] in",
                "completion: { [weak inputMediaNode] _ in",
            ),
            "ChatListFilterPresetListController.swift": (
                "|> map { [updatedFilterOrder] presentationData, state, filtersWithCountsValue, preferences, updatedFilterOrderValue, suggestedFilters, peer, allLimits, displayTags -> (ItemListControllerState, (ItemListNodeState, Any)) in",
                "startStandalone(next: { [weak updatedFilterOrder] updatedFilterOrderValue in",
            ),
            "ChatContextMenus.swift": (
                "|> mapToSignal { [chatListController] peerGroup, recentlySearchedPeers, limitsData -> Signal<[ContextMenuItem], NoError> in",
                "|> mapToSignal { [chatListController] peer, peerNotificationSettings, threadData, globalNotificationSettings -> Signal<[ContextMenuItem], NoError> in",
            ),
            "ChatListController.swift": (
                "action: { [self] c, f in",
                "Queue.mainQueue().after(1.0, { [self] in",
                "startStandalone(next: { [sourceController] peer in",
                "Queue.mainQueue().after(0.5) { [self] in",
            ),
        }
        for filename, captures in expected_captures.items():
            source = (ROOT / "submodules/ChatListUI/Sources" / filename).read_text(encoding="utf-8")
            with self.subTest(file=filename):
                for capture in captures:
                    self.assertTrue(capture in source, f"{filename} is missing explicit capture: {capture!r}")

    def test_inline_search_entry_mapping_explicitly_captures_outer_component(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatInlineSearchResultsListComponent/Sources/ChatInlineSearchResultsListComponent.swift"
        ).read_text(encoding="utf-8")
        self.assertTrue(
            "let entryToItem: (Entry) -> ListViewItem = { [self] entry -> ListViewItem in" in source,
            "entry mapping should explicitly capture its component before the nested weak action",
        )
        self.assertIn("action: { [weak self] peer in", source)

    def test_standalone_color_picker_explicitly_captures_attachment_controller(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Settings/WallpaperGridScreen/Sources/ThemeColorsGridController.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("controller.requestController = { [controller] _, present in", source)
        self.assertIn("colorPickerController.dismissControllers = { [weak controller] in", source)

    def test_peer_selection_forward_menu_explicitly_captures_chat_controller(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/PeerSelectionController/Sources/PeerSelectionControllerNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "|> map { [chatController] forwardOptions, messages, messagesCount -> [ContextMenuItem] in",
            source,
        )
        self.assertIn("action: { [weak self, weak chatController] c, f in", source)

    def test_peer_selection_paywall_explicitly_weak_captures_controller_alias(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/PeerSelectionController/Sources/PeerSelectionControllerNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "openPremiumPaywall: { [weak selfController = strongSelf.controller] c in",
            source,
        )
        self.assertIn("selfController.push(c)", source)

    def test_animated_sticker_tap_explicitly_captures_node_for_weak_configuration_callback(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageAnimatedStickerItemNode/Sources/ChatMessageAnimatedStickerItemNode.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "let emojiTapAction: (Bool) -> InternalBubbleTapAction? = { [self] shouldPlay in",
            source,
        )
        self.assertIn(
            ").startStandalone(next: { [weak self] appConfiguration in",
            source,
        )

    def test_browser_save_callback_explicitly_captures_owner_for_weak_archive_callback(self):
        source = (ROOT / "submodules/BrowserUI/Sources/BrowserWebContent.swift").read_text(encoding="utf-8")
        self.assertIn(
            'self.webView.evaluateJavaScript("document.contentType") { [self] result, _ in',
            source,
        )
        self.assertIn("self.webView.createWebArchiveData { [weak self] result in", source)

    def test_reply_count_layout_explicitly_captures_owner_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Chat/ChatMessageItemImpl/Sources/ChatReplyCountItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("return { [self] item, params, dateAtBottom in", source)
        self.assertIn("{ [weak self] in", source)

    def test_rank_chat_preview_layout_explicitly_captures_owner_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/RankChatPreviewItem/Sources/RankChatPreviewItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("return { [self] item, params, neighbors in", source)
        self.assertIn("return (layout, { [weak self] in", source)

    def test_web_app_chat_preview_layout_explicitly_captures_owner_for_weak_apply(self):
        source = (ROOT / "submodules/WebUI/Sources/WebAppMessageChatPreviewItem.swift").read_text(encoding="utf-8")
        self.assertIn("return { [self] item, params, neighbors in", source)
        self.assertIn("return (layout, { [weak self] in", source)

    def test_web_app_delayed_scroll_explicitly_captures_owner_for_weak_callback(self):
        source = (ROOT / "submodules/WebUI/Sources/WebAppController.swift").read_text(encoding="utf-8")
        self.assertIn("Queue.mainQueue().after(0.4, { [self] in", source)
        self.assertIn("completion: { [weak self] contentOffset in", source)

    def test_web_app_export_completion_explicitly_captures_controller_for_weak_picker(self):
        source = (ROOT / "submodules/WebUI/Sources/WebAppController.swift").read_text(encoding="utf-8")
        self.assertIn("completion: { [weak self, controller] resultUrl, _ in", source)
        self.assertIn("completion: { [weak self, weak controller] urls in", source)

    def test_web_app_terms_callback_explicitly_captures_owner_for_weak_presentation(self):
        source = (ROOT / "submodules/WebUI/Sources/WebAppController.swift").read_text(encoding="utf-8")
        self.assertIn("startStandalone(next: { [self] resolvedUrl in", source)
        self.assertIn("present: { [weak self] c, arguments in", source)

    def test_peer_name_color_preview_explicitly_captures_owner_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Settings/PeerNameColorScreen/Sources/PeerNameColorChatPreviewItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("return { [self] item, params, neighbors in", source)
        self.assertIn("return (layout, { [weak self] in", source)

    def test_emoji_picker_layout_explicitly_captures_owner_for_weak_apply(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Settings/PeerNameColorScreen/Sources/EmojiPickerItem.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("return { [self] item, params, neighbors in", source)
        self.assertIn("return (layout, { [weak self] in", source)

    def test_profile_gift_purchase_callbacks_keep_weak_nested_owners_explicit(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Settings/PeerNameColorScreen/Sources/UserApperanceScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("let proceed: () -> Void = { [self] in", source)
        self.assertIn("start(error: { [weak self, weak controller] error in", source)
        self.assertIn("}, completed: { [weak self] in", source)
        self.assertIn(
            "startStandalone(next: { [weak self, weak controller, starsContext] options in",
            source,
        )
        self.assertIn("completion: { [weak self, weak starsContext] stars in", source)

    def test_business_intro_picker_completion_explicitly_captures_owner_for_weak_editor(self):
        source = (
            ROOT
            / "submodules/TelegramUI/Components/Settings/BusinessIntroSetupScreen/Sources/BusinessIntroSetupScreen.swift"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "completion: { [self] result, transitionView, transitionRect, transitionImage, fromCamera, completion, cancelled in",
            source,
        )
        self.assertIn("completion: { [weak self] file, emoji, commit in", source)

    def test_settings_layout_factories_capture_owner_before_weak_apply(self):
        expected_counts = {
            "Data and Storage/AutodownloadDataUsagePickerItem.swift": 1,
            "Data and Storage/AutodownloadSizeLimitItem.swift": 1,
            "Notifications/NotificationsCategoryItemListItem.swift": 1,
            "Privacy and Security/ForwardPrivacyChatPreviewItem.swift": 1,
            "Privacy and Security/GlobalAutoremoveHeaderItem.swift": 1,
            "Privacy and Security/Recent Sessions/RecentSessionsHeaderItem.swift": 1,
            "Data and Storage/CalculatingCacheSizeItem.swift": 1,
            "Data and Storage/EnergyUsageBatteryLevelItem.swift": 1,
            "Data and Storage/KeepMediaDurationPickerItem.swift": 1,
            "Data and Storage/MaximumCacheSizePickerItem.swift": 1,
            "Data and Storage/ProxySettingsActionItem.swift": 1,
            "Text Size/TextSizeSelectionItem.swift": 1,
            "ThemePickerGridItem.swift": 1,
            "Privacy and Security/Recent Sessions/ItemListRecentSessionItem.swift": 1,
            "Privacy and Security/Recent Sessions/ItemListWebsiteItem.swift": 2,
            "Data and Storage/ProxySettingsServerItem.swift": 1,
            "Data and Storage/WebBrowserDomainExceptionItem.swift": 1,
            "Data and Storage/WebBrowserItem.swift": 1,
            "Search/SettingsSearchResultItem.swift": 1,
            "Themes/ThemeSettingsAccentColorItem.swift": 1,
            "Themes/ThemeSettingsAppIconItem.swift": 1,
            "Themes/ThemeSettingsBrightnessItem.swift": 1,
            "Themes/ThemeSettingsChatPreviewItem.swift": 1,
            "Themes/ThemeSettingsFontSizeItem.swift": 1,
            "DeleteAccountPeersItem.swift": 1,
            "DeleteAccountPhoneItem.swift": 1,
        }
        settings_root = ROOT / "submodules/SettingsUI/Sources"
        for relative_path, expected_count in expected_counts.items():
            source_lines = (settings_root / relative_path).read_text(encoding="utf-8").splitlines()
            with self.subTest(file=relative_path):
                self.assertEqual(
                    sum(line.strip() == "return { [self] item, params, neighbors in" for line in source_lines),
                    expected_count,
                    f"{relative_path} must explicitly capture its owner before weak apply callbacks",
                )

    def test_settings_nested_weak_captures_have_explicit_outer_owners(self):
        settings_root = ROOT / "submodules/SettingsUI/Sources"
        layout_sources = (
            "Data and Storage/AutodownloadDataUsagePickerItem.swift",
            "Data and Storage/AutodownloadSizeLimitItem.swift",
            "Notifications/NotificationsCategoryItemListItem.swift",
            "Privacy and Security/ForwardPrivacyChatPreviewItem.swift",
            "Privacy and Security/GlobalAutoremoveHeaderItem.swift",
            "Privacy and Security/Recent Sessions/RecentSessionsHeaderItem.swift",
            "Data and Storage/CalculatingCacheSizeItem.swift",
            "Data and Storage/EnergyUsageBatteryLevelItem.swift",
            "Data and Storage/KeepMediaDurationPickerItem.swift",
            "Data and Storage/MaximumCacheSizePickerItem.swift",
            "Data and Storage/ProxySettingsActionItem.swift",
            "Text Size/TextSizeSelectionItem.swift",
            "ThemePickerGridItem.swift",
            "Privacy and Security/Recent Sessions/ItemListRecentSessionItem.swift",
            "Privacy and Security/Recent Sessions/ItemListWebsiteItem.swift",
            "Data and Storage/ProxySettingsServerItem.swift",
            "Data and Storage/WebBrowserDomainExceptionItem.swift",
            "Data and Storage/WebBrowserItem.swift",
            "Search/SettingsSearchResultItem.swift",
            "Themes/ThemeSettingsAccentColorItem.swift",
            "Themes/ThemeSettingsAppIconItem.swift",
            "Themes/ThemeSettingsBrightnessItem.swift",
            "Themes/ThemeSettingsChatPreviewItem.swift",
            "Themes/ThemeSettingsFontSizeItem.swift",
            "DeleteAccountPeersItem.swift",
            "DeleteAccountPhoneItem.swift",
        )
        for relative_path in layout_sources:
            source = (settings_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(file=relative_path):
                self.assertIn("[weak self]", source)

        custom_captures = {
            "Data and Storage/DataAndStorageSettingsController.swift": (
                "toggleSensitiveContent: { [contentSettingsConfiguration] value in",
                "[weak contentSettingsConfiguration] settings in",
            ),
            "DeleteAccountOptionsController.swift": (
                "replaceTopControllerImpl = { [weak navigationController, controller] c, complex in",
                "[weak navigationController, weak controller, weak c] in",
            ),
            "Language Selection/LocalizationListControllerNode.swift": (
                "let removeItem: (String) -> Void = { [self] id in",
                "start(next: { [weak self] info in",
            ),
            "Privacy and Security/PasscodeOptionsController.swift": (
                "turnPasscodeOff: { [passcodeOptionsDataPromise] in",
                "let setAction: (Int32?) -> Void = { [passcodeOptionsDataPromise] value in",
                "changeTouchId: { [passcodeOptionsDataPromise] value in",
            ),
        }
        for relative_path, expected_captures in custom_captures.items():
            source = (settings_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(file=relative_path):
                for capture in expected_captures:
                    self.assertIn(capture, source)

        privacy = (settings_root / "Privacy and Security/PrivacyAndSecurityController.swift").read_text(encoding="utf-8")
        for callback in (
            "openLastSeenPrivacy",
            "openGroupsPrivacy",
            "openVoiceCallPrivacy",
            "openProfilePhotoPrivacy",
            "openForwardPrivacy",
            "openPhoneNumberPrivacy",
            "openVoiceMessagePrivacy",
            "openBioPrivacy",
            "openBirthdayPrivacy",
            "openSavedMusicPrivacy",
            "openGiftsPrivacy",
        ):
            self.assertIn(f"{callback}: {{ [currentInfoDisposable] in", privacy)
        self.assertIn("setupAccountAutoremove: { [updateAccountTimeoutDisposable] in", privacy)
        self.assertIn("[weak currentInfoDisposable]", privacy)
        self.assertIn("[weak updateAccountTimeoutDisposable]", privacy)

    def test_peer_info_nested_callbacks_explicitly_capture_outer_owners(self):
        peer_info_root = ROOT / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources"
        pane = (peer_info_root / "PeerInfoPaneContainerNode.swift").read_text(encoding="utf-8")
        self.assertIn("Queue.mainQueue().after(0.15) { [self] in", pane)
        self.assertIn("start(completed: { [weak self] in", pane)

        screen = (peer_info_root / "PeerInfoScreen.swift").read_text(encoding="utf-8")
        self.assertIn("start(next: { [self] verifierIcon in", screen)
        self.assertIn("openContextMenu: { [self] item, sourceNode, rect, gesture in", screen)
        self.assertIn("startStandalone(next: { [sourceController] peer in", screen)
        self.assertIn("action: { [weak sourceController] _, a in", screen)

        avatar_setup = (peer_info_root / "PeerInfoScreenAvatarSetup.swift").read_text(encoding="utf-8")
        self.assertIn(
            "completion: { [weak self, parentController] result, transitionView, transitionRect, transitionImage, fromCamera, transitionOut, cancelled in",
            avatar_setup,
        )
        self.assertIn("willComplete: { [weak self, weak parentController] image, isVideo, commit in", avatar_setup)
        self.assertIn("|> mapToSignal { [self] exportSubject, duration in", avatar_setup)
        self.assertIn("startStandalone(next: { [weak self] status in", avatar_setup)

        gifts = (peer_info_root / "PeerInfoScreenDisplayGiftsContextMenu.swift").read_text(encoding="utf-8")
        self.assertIn(
            "|> map { [self, weak pane, weak giftsContext] filter, sorting, canReorder -> ContextController.Items in",
            gifts,
        )
        self.assertIn("action: { [weak self] _, f in", gifts)

        open_peer = (peer_info_root / "PeerInfoScreenOpenPeerInfoContextMenu.swift").read_text(encoding="utf-8")
        self.assertIn("startStandalone(next: { [weak self, sourceNode] sharedData in", open_peer)
        self.assertIn("sourceNodeAndRect: { [weak self, weak sourceNode] in", open_peer)

    def test_business_simple_link_strings_accept_dynamic_values(self):
        source = (ROOT / "Telegram/Telegram-iOS/en.lproj/Localizable.strings").read_text(encoding="utf-8")
        expected_entries = (
            '"Business.Links.SimpleLinkInfoUsernamePhone" = "You can also use a simple link for a chat with you — [%1$@](username) or [%2$@](phone).";',
            '"Business.Links.SimpleLinkInfoUsername" = "You can also use a simple link for a chat with you — [%1$@](username).";',
            '"Business.Links.SimpleLinkInfoPhone" = "You can also use a simple link for a chat with you — [%1$@](phone).";',
        )
        for entry in expected_entries:
            key = entry.partition('"')[2].partition('"')[0]
            with self.subTest(entry=entry):
                self.assertTrue(entry in source, f"missing formatted business link resource: {key}")

    def test_statistics_layouts_explicitly_capture_outer_nodes(self):
        expected = {
            "StarsTransactionItem.swift": "return { [self] item, params, neighbors in",
            "StatsOverviewItem.swift": "return { [self] item, params, neighbors in",
            "StatsGraphItem.swift": "return { [self] item, params, neighbors in",
            "StatsMessageItem.swift": "return { [self] item, params, neighbors in",
            "MonetizationBalanceItem.swift": "return { [self] item, params, neighbors in",
            "BoostLevelHeaderItem.swift": "return { [self] item, params, neighbors in",
            "BoostsTabsItem.swift": "return { [self] item, params, neighbors in",
        }
        for filename, capture in expected.items():
            source = (ROOT / "submodules/StatisticsUI/Sources" / filename).read_text(encoding="utf-8")
            with self.subTest(file=filename):
                self.assertTrue(capture in source, f"{filename} should explicitly capture its outer layout node")

        graph = (ROOT / "submodules/StatisticsUI/Sources/StatsGraphItem.swift").read_text(encoding="utf-8")
        self.assertIn("getDetailsData: { [weak self] date, completion in", graph)
        self.assertIn("return (ListViewItemNodeLayout(contentSize: contentSize, insets: insets), { [weak self] in", graph)


if __name__ == "__main__":
    unittest.main()
