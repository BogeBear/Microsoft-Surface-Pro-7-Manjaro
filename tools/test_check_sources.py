"""Regressionstester för check_sources.py med TemporaryDirectory och subprocess."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestCheckSources(unittest.TestCase):
    """Testfall för check_sources.py."""

    def setUp(self):
        """Skapa en temporär mapp för varje test."""
        self.tmpdir = Path(tempfile.mkdtemp())
        self.tools_dir = self.tmpdir / "tools"
        self.integration_dir = self.tmpdir / "integration"
        self.tools_dir.mkdir()
        self.integration_dir.mkdir()

    def tearDown(self):
        """Rensa efter test."""
        import shutil
        shutil.rmtree(self.tmpdir)

    def _copy_tool(self, src_file):
        """Kopiera verktygsfilen till temporär mapp."""
        self.tools_dir.joinpath("check_sources.py").write_text(src_file)

    def _run_tool(self):
        """Kör verktyget och returnera exit code och output."""
        tool_path = self.tools_dir / "check_sources.py"
        result = subprocess.run(
            [sys.executable, str(tool_path)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(self.tools_dir)
        )
        return result.returncode, result.stdout, result.stderr

    def test_valid_py_sh(self):
        """(a) Giltig .py och .sh ska ge exit 0 och 'Syntax-checked files: 2'."""
        py_content = "#!/usr/bin/env python3\nprint('hello')\n"
        sh_content = "#!/bin/bash\necho 'hello'\n"
        self.integration_dir.joinpath("test.py").write_text(py_content)
        self.integration_dir.joinpath("test.sh").write_text(sh_content)

        self._copy_tool(Path(__file__).with_name("check_sources.py").read_text())
        exit_code, stdout, _ = self._run_tool()

        self.assertEqual(exit_code, 0, f"Exit code ska vara 0, fick: {exit_code}")
        self.assertIn("Syntax-checked files: 2", stdout)

    def test_nested_directories(self):
        """(b) Kataloger integration/package.py/ och integration/package.sh/ ska ge exit 0 och count 2."""
        # Skapa underkataloger med suffix .py och .sh
        (self.integration_dir / "package.py").mkdir()
        (self.integration_dir / "package.sh").mkdir()
        # Skriv Pythonfilen till underkatalogen
        (self.integration_dir / "package.py" / "nested.py").write_text(py_content := "#!/usr/bin/env python3\nprint('nested')\n")
        # Skriv Bashfilen till underkatalogen
        (self.integration_dir / "package.sh" / "nested.sh").write_text(sh_content := "#!/bin/bash\necho 'nested'\n")

        self._copy_tool(Path(__file__).with_name("check_sources.py").read_text())
        exit_code, stdout, _ = self._run_tool()

        self.assertEqual(exit_code, 0, f"Exit code ska vara 0, fick: {exit_code}")
        self.assertIn("Syntax-checked files: 2", stdout)

    def test_broken_python(self):
        """(c) Python med 'def broken(: ska ge icke-noll exit."""
        broken_py = "def broken(:\n    pass\n"
        (self.integration_dir / "broken.py").write_text(broken_py)

        self._copy_tool(Path(__file__).with_name("check_sources.py").read_text())
        exit_code, _, _ = self._run_tool()

        self.assertNotEqual(exit_code, 0, "Exit code ska inte vara 0 för ogiltig Python")

    def test_broken_bash(self):
        """(d) Bash med 'if true; then' utan fi ska ge icke-noll exit."""
        broken_sh = "if true; then\necho 1\n"  # Saknar fi

        (self.integration_dir / "broken.sh").write_text(broken_sh)

        self._copy_tool(Path(__file__).with_name("check_sources.py").read_text())
        exit_code, _, _ = self._run_tool()

        self.assertNotEqual(exit_code, 0, "Exit code ska inte vara 0 för ogiltig Bash")


if __name__ == "__main__":
    unittest.main()
