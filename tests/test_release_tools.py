import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.release_notes import extract_release_notes


class ReleaseNotesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.changelog = (
            Path(__file__).resolve().parents[1] / "CHANGELOG.md"
        ).read_text(encoding="utf-8")

    def test_extracts_version_010_notes(self) -> None:
        notes = extract_release_notes(self.changelog, "0.1.0")
        self.assertIn("Aplicativo desktop inicial", notes)
        self.assertIn("Nenhuma remocao", notes)

    def test_extracts_version_020_notes(self) -> None:
        notes = extract_release_notes(self.changelog, "0.2.0")
        self.assertIn("Pagina Sobre", notes)
        self.assertIn("Executavel Windows x64 portatil", notes)

    def test_extracts_version_040_notes(self) -> None:
        notes = extract_release_notes(self.changelog, "0.4.0")
        self.assertIn("Aba Devices", notes)
        self.assertIn("Análise de versão", notes)
        self.assertIn("Nenhuma remocao", notes)

    def test_rejects_unknown_version(self) -> None:
        with self.assertRaises(ValueError):
            extract_release_notes(self.changelog, "9.9.9")


if __name__ == "__main__":
    unittest.main()
