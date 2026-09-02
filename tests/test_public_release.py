from __future__ import annotations

import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SKILL_DIR


class PublicReleaseTests(unittest.TestCase):
    def test_public_tree_has_no_personal_demo_or_live_manifest(self) -> None:
        self.assertFalse((PROJECT_DIR / "hosts.json").exists())
        self.assertFalse((PROJECT_DIR / "hosts.local.json").exists())
        demo_names = [path.name.casefold() for path in (PROJECT_DIR / "examples").rglob("*")]
        personal_slug = "ranzhuo" + "ran"
        self.assertFalse(any(personal_slug in name for name in demo_names))

    def test_public_text_uses_only_synthetic_examples(self) -> None:
        fragments = [
            "back_" + "new_bu",
            "biaozhu_" + "platform",
            "report-" + "server",
            "proje" + "cket",
            "10." + "191.",
            "/n" + "fs/ofs-" + "llm-ssd",
            "/Us" + "ers/" + "di" + "di",
            "lu" + "ban",
            "航班低价" + "推荐字段",
            "本地 Redis" + " 访问链路问题",
            "10:30–12:00、" + "14:00–18:00、19:00–21:00",
        ]
        inspected = []
        for path in PROJECT_DIR.rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".yaml", ".html", ".json", ".py"}:
                continue
            inspected.append(path)
            text = path.read_text(encoding="utf-8")
            for fragment in fragments:
                self.assertNotIn(fragment, text, f"personal example in {path}")
        self.assertTrue(inspected)

    def test_skill_tree_contains_no_compiled_or_os_metadata(self) -> None:
        forbidden = [
            path
            for path in SKILL_DIR.rglob("*")
            if path.is_file() and (path.suffix == ".pyc" or path.name == ".DS_Store")
        ]
        self.assertEqual(forbidden, [])

    def test_public_repository_contains_release_documents(self) -> None:
        for name in ["README.md", "README.en.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md"]:
            self.assertTrue((PROJECT_DIR / name).is_file(), name)
        for image in ["daily-timeline.png", "weekly-report.png"]:
            self.assertTrue((PROJECT_DIR / "docs" / "images" / image).is_file(), image)


if __name__ == "__main__":
    unittest.main()
