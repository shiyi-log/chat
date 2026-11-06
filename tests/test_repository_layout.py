from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MARKERS = {
    "server": "go.mod",
    "clients/android": "settings.gradle",
    "clients/ios": "Telegram/BUILD",
    "clients/desktop": "CMakeLists.txt",
    "docs": "README.md",
}


class RepositoryLayoutTest(unittest.TestCase):
    def test_root_readme_is_chinese_first(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Chat 聊天系统"))
        self.assertIn("## English Summary", readme)

    def test_current_product_readmes_use_chat_branding(self):
        readmes = (
            "README.md",
            "docs/README.md",
            "server/README.md",
            "server/README-zh.md",
            "clients/android/README.md",
            "clients/desktop/README.md",
            "clients/ios/README.md",
        )
        for relative_path in readmes:
            with self.subTest(path=relative_path):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("Private Chat", text)

    def test_all_suite_sources_are_present_without_nested_git_repositories(self):
        for component, marker in SOURCE_MARKERS.items():
            with self.subTest(component=component):
                component_root = ROOT / component
                self.assertTrue((component_root / marker).is_file())
                self.assertFalse((component_root / ".git").exists())


if __name__ == "__main__":
    unittest.main()
