import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


class LayerBoundaryTests(unittest.TestCase):
    def test_core_services_and_models_do_not_import_walk_detection(self):
        offenders = []
        paths = list((BACKEND / "services").glob("*.py")) + list((BACKEND / "models").glob("*.py"))
        for path in paths:
            if path.name == "walk_detection.py":
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "walk_detection" in node.module:
                    offenders.append(str(path.relative_to(BACKEND)))
                if isinstance(node, ast.Import) and any("walk_detection" in alias.name for alias in node.names):
                    offenders.append(str(path.relative_to(BACKEND)))
        self.assertEqual(offenders, [])

    def test_backend_boots_when_layer_two_files_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "backend"
            shutil.copytree(
                BACKEND,
                copy,
                ignore=shutil.ignore_patterns("__pycache__", "tests", "build", "dist", "*.db"),
            )
            for relative in (
                "services/walk_detection.py",
                "routers/walk_detection.py",
                "models/walk_detection.py",
                "migrations/m002_walk_detection.py",
            ):
                (copy / relative).unlink()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import main; assert not any(r.path.startswith('/api/walk-detection') for r in main.app.routes)",
                ],
                cwd=copy,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
