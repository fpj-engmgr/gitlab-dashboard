#!/usr/bin/env python3
"""
Migration script to add group_id column to existing tables.
Run this before upgrading to multi-group support.
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def check_column_exists(cursor, table, column):
    """Check if column exists in table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_database():
    """Add group_id column to all tables and populate with default."""
    db_path = settings.database_url.replace('sqlite:///', './')

    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        print("No migration needed - tables will be created with group_id on first run")
        return True

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = ['merge_requests', 'commits', 'comments', 'contributors']
    default_group = "default"

    print(f"Starting migration to add group_id column...")
    print(f"Default group ID: {default_group}")
    print()

    for table in tables:
        if check_column_exists(cursor, table, 'group_id'):
            print(f"✓ {table}.group_id already exists")
            continue

        try:
            # Add column
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN group_id TEXT")
            print(f"✓ Added {table}.group_id column")

            # Populate existing rows
            cursor.execute(f"UPDATE {table} SET group_id = ? WHERE group_id IS NULL", (default_group,))
            affected = cursor.rowcount
            print(f"  Updated {affected} existing rows with default group")

            # Create index for performance
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_group_id ON {table}(group_id)")
            print(f"✓ Created index on {table}.group_id")
            print()

        except sqlite3.Error as e:
            print(f"✗ Error migrating {table}: {e}")
            conn.rollback()
            return False

    conn.commit()
    conn.close()

    print("✓ Migration completed successfully!")
    print("You can now configure multi-group support via groups.json")
    return True


if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)
