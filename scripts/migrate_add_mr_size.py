#!/usr/bin/env python3
"""
Database migration: Add MR size tracking fields
Adds lines_added, lines_deleted, and lines_changed columns to merge_requests table.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

def migrate():
    """Add MR size columns to database."""
    db_path = settings.database_url.replace('sqlite:///', '')

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(merge_requests)")
    columns = [row[1] for row in cursor.fetchall()]

    migrations_needed = []
    if 'lines_added' not in columns:
        migrations_needed.append('lines_added')
    if 'lines_deleted' not in columns:
        migrations_needed.append('lines_deleted')
    if 'lines_changed' not in columns:
        migrations_needed.append('lines_changed')

    if not migrations_needed:
        print("✅ All MR size columns already exist. No migration needed.")
        conn.close()
        return

    print(f"Adding columns: {', '.join(migrations_needed)}")

    try:
        # Add new columns
        if 'lines_added' in migrations_needed:
            cursor.execute("ALTER TABLE merge_requests ADD COLUMN lines_added INTEGER")
            print("  ✅ Added lines_added column")

        if 'lines_deleted' in migrations_needed:
            cursor.execute("ALTER TABLE merge_requests ADD COLUMN lines_deleted INTEGER")
            print("  ✅ Added lines_deleted column")

        if 'lines_changed' in migrations_needed:
            cursor.execute("ALTER TABLE merge_requests ADD COLUMN lines_changed INTEGER")
            print("  ✅ Added lines_changed column")

        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nNote: Existing MRs will have NULL for these fields.")
        print("Run 'Refresh Data' in the dashboard to populate size data for new MRs.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
