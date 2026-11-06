import re
import unittest
from pathlib import Path


SQL_DIR = Path(__file__).resolve().parent
TABLE = "chat_invite_participants"


def table_columns():
    schema = (SQL_DIR / "1_teamgram.sql").read_text()
    match = re.search(
        rf"CREATE TABLE `{TABLE}`\s*\((.*?)\) ENGINE=",
        schema,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"CREATE TABLE for {TABLE} not found")

    columns = set(re.findall(r"^\s*`([^`]+)`\s+", match.group(1), re.MULTILINE))
    for path in sorted(SQL_DIR.glob("migrate-*.sql")):
        if path.name >= "migrate-20260309.sql":
            continue
        for statement in re.findall(
            rf"ALTER TABLE `{TABLE}`(.*?);",
            path.read_text(),
            re.IGNORECASE | re.DOTALL,
        ):
            columns.update(
                re.findall(
                    r"\bADD(?:\s+COLUMN)?\s+`([^`]+)`\s+",
                    statement,
                    re.IGNORECASE,
                )
            )
    return columns


def added_indexes(sql):
    indexes = {}
    for statement in re.findall(
        rf"ALTER TABLE `{TABLE}`(.*?);",
        sql,
        re.IGNORECASE | re.DOTALL,
    ):
        for name, fields in re.findall(
            r"\bADD\s+(?:UNIQUE\s+)?KEY\s+`([^`]+)`\s*\(([^)]+)\)",
            statement,
            re.IGNORECASE,
        ):
            indexes[name] = tuple(re.findall(r"`([^`]+)`", fields))
    return indexes


class Migration20260309Test(unittest.TestCase):
    def test_added_chat_invite_participant_indexes_use_existing_columns(self):
        migration = (SQL_DIR / "migrate-20260309.sql").read_text()
        columns = table_columns()
        indexes = added_indexes(migration)
        self.assertTrue(indexes, "No chat invite participant indexes found")

        for index_name, index_columns in indexes.items():
            missing = set(index_columns) - columns
            self.assertFalse(
                missing,
                f"{index_name} references columns missing from {TABLE}: {sorted(missing)}",
            )


if __name__ == "__main__":
    unittest.main()
