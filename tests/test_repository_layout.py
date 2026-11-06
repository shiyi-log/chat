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
        self.assertTrue(readme.startswith("# Private Chat 私有聊天系统"))
        self.assertIn("## English Summary", readme)

    def test_all_suite_sources_are_present_without_nested_git_repositories(self):
        for component, marker in SOURCE_MARKERS.items():
            with self.subTest(component=component):
                component_root = ROOT / component
                self.assertTrue((component_root / marker).is_file())
                self.assertFalse((component_root / ".git").exists())


if __name__ == "__main__":
    unittest.main()
