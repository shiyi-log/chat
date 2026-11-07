import csv
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "server/teamgramd/deploy/sql"


class ServerChatBrandingTest(unittest.TestCase):
    def test_system_account_seed_uses_chat_identity(self):
        sql = (SQL_DIR / "z_init.sql").read_text(encoding="utf-8")
        insert = re.search(
            r"INSERT INTO users \((?P<columns>[^)]*)\) VALUES\((?P<values>[^;]*)\);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(insert, "System account seed was not found")

        columns = [column.strip() for column in insert.group("columns").split(",")]
        values = next(
            csv.reader(
                [insert.group("values")],
                delimiter=",",
                quotechar="'",
                skipinitialspace=True,
            )
        )
        self.assertEqual(len(columns), len(values), "System account seed column/value count differs")
        account = dict(zip(columns, values))

        self.assertEqual("777000", account["id"])
        self.assertEqual("Chat", account["first_name"])
        self.assertEqual("", account["username"])

    def test_existing_system_account_has_chat_brand_migration(self):
        migration = SQL_DIR / "migrate-20261107.sql"
        self.assertTrue(migration.is_file(), "Missing system account branding migration")
        sql = migration.read_text(encoding="utf-8")
        update = re.search(
            r"UPDATE\s+users\s+SET\s+(?P<assignments>.*?)\s+WHERE\s+id\s*=\s*777000\s+AND\s+first_name\s*=\s*'Teamgram';",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(update, "Migration must only rename the legacy system account")

        assignments = update.group("assignments")
        self.assertIn("first_name = 'Chat'", assignments)
        self.assertIn("username = CASE WHEN username = 'teamgram' THEN '' ELSE username END", assignments)


if __name__ == "__main__":
    unittest.main()
