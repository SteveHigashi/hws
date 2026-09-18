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
