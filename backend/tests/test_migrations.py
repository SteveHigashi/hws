import ast
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from migrations.runner import apply_migrations  # noqa: E402


class MigrationTests(unittest.TestCase):
    def test_existing_bot_table_is_upgraded_idempotently(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = create_engine(f"sqlite:///{Path(temporary) / 'legacy.db'}")
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE TABLE bot_visits (id VARCHAR(32) PRIMARY KEY, bot_name VARCHAR(64) NOT NULL)"
                ))
                apply_migrations(connection)
                apply_migrations(connection)
                columns = {column["name"] for column in inspect(connection).get_columns("bot_visits")}
                tables = set(inspect(connection).get_table_names())
            self.assertTrue({
                "verification_state", "verification_method", "ip_hash",
                "http_status", "response_bytes", "referrer",
            }.issubset(columns))
            self.assertIn("walk_detection_runs", tables)


if __name__ == "__main__":
    unittest.main()


class RevisionUniquenessTests(unittest.TestCase):
    """Two migrations must never claim the same revision.

    Added 2026-09-24 after the log-source work arrived numbered m006, colliding
    with m006_password_resets and m007_passkeys which were already applied in
    production. The whole suite passed with the collision in place — 128 green —
    so nothing would have stopped it reaching the box. Broken on purpose before
    this was written: setting m008's REVISION back to 006 now fails here.
    """

    def _migration_files(self):
        directory = Path(__file__).resolve().parents[1] / "migrations"
        return sorted(p for p in directory.glob("m[0-9][0-9][0-9]_*.py"))

    def test_every_revision_is_unique(self):
        seen = {}
        for path in self._migration_files():
            revision = self._revision_of(path)
            self.assertNotIn(
                revision, seen,
                f"{path.name} and {seen.get(revision)} both claim revision {revision!r}",
            )
            seen[revision] = path.name
        self.assertGreaterEqual(len(seen), 8)

    def test_revision_matches_the_file_number(self):
        for path in self._migration_files():
            with self.subTest(migration=path.name):
                number = path.name[1:4]
                self.assertTrue(
                    self._revision_of(path).startswith(number),
                    f"{path.name} declares revision {self._revision_of(path)!r}, "
                    f"which does not start with {number}",
                )

    def _revision_of(self, path):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "REVISION":
                        return ast.literal_eval(node.value)
        self.fail(f"{path.name} has no REVISION constant")
