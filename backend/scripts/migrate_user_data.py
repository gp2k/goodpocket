"""
Migrate user data from one account to another.
Usage: python scripts/migrate_user_data.py

This script transfers all bookmarks and clusters from one user to another.
"""
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app import database as db


async def get_user_id_by_email(email: str) -> str | None:
    """Get user_id from Supabase auth.users by email."""
    # Query auth.users table (requires service role)
    row = await db.fetchrow(
        """
        SELECT id FROM auth.users WHERE email = $1
        """,
        email
    )
    return str(row["id"]) if row else None


async def migrate_user_data(from_email: str, to_email: str, auto_confirm: bool = False):
    """Migrate all data from one user to another."""
    
    print(f"Connecting to database...")
    await db.init_db()
    
    try:
        # Get user IDs
        print(f"Finding user ID for {from_email}...")
        from_user_id = await get_user_id_by_email(from_email)
        if not from_user_id:
            print(f"ERROR: User {from_email} not found!")
            return
        print(f"  -> {from_user_id}")
        
        print(f"Finding user ID for {to_email}...")
        to_user_id = await get_user_id_by_email(to_email)
        if not to_user_id:
            print(f"ERROR: User {to_email} not found!")
            print("Make sure you've logged in with OAuth at least once.")
            return
        print(f"  -> {to_user_id}")
        
        if from_user_id == to_user_id:
            print("ERROR: Source and target users are the same!")
            return
        
        # Count existing data
        from_bookmarks = await db.fetchrow(
            "SELECT COUNT(*) as count FROM bookmarks WHERE user_id = $1",
            from_user_id
        )
        from_clusters = await db.fetchrow(
            "SELECT COUNT(*) as count FROM clusters WHERE user_id = $1",
            from_user_id
        )
        
        print(f"\nData to migrate from {from_email}:")
        print(f"  - Bookmarks: {from_bookmarks['count']}")
        print(f"  - Clusters: {from_clusters['count']}")
        
        if from_bookmarks['count'] == 0:
            print("\nNo data to migrate!")
            return
        
        # Check for conflicts (same URL in both accounts)
        conflicts = await db.fetchrow(
            """
            SELECT COUNT(*) as count FROM bookmarks b1
            WHERE b1.user_id = $1 
            AND EXISTS (
                SELECT 1 FROM bookmarks b2 
                WHERE b2.user_id = $2 AND b2.url = b1.url
            )
            """,
            from_user_id, to_user_id
        )
        
        if conflicts['count'] > 0:
            print(f"\nWARNING: {conflicts['count']} bookmarks have the same URL in both accounts.")
            print("These will be skipped (target account's version will be kept).")
        
        # Confirm migration
        print(f"\nReady to migrate data from {from_email} to {to_email}")
        if not auto_confirm:
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                print("Migration cancelled.")
                return
        else:
            print("Auto-confirmed with --yes flag")
        
        # Migrate bookmarks (skip duplicates)
        print("\nMigrating bookmarks...")
        result = await db.execute(
            """
            UPDATE bookmarks 
            SET user_id = $2
            WHERE user_id = $1
            AND NOT EXISTS (
                SELECT 1 FROM bookmarks b2 
                WHERE b2.user_id = $2 AND b2.url = bookmarks.url
            )
            """,
            from_user_id, to_user_id
        )
        print(f"  -> Bookmarks migrated: {result}")
        
        # Delete old clusters (they'll be regenerated)
        print("Deleting old clusters...")
        await db.execute(
            "DELETE FROM clusters WHERE user_id = $1",
            from_user_id
        )
        await db.execute(
            "DELETE FROM clusters WHERE user_id = $1",
            to_user_id
        )
        print("  -> Old clusters deleted (run batch job to regenerate)")
        
        # Verify migration
        new_count = await db.fetchrow(
            "SELECT COUNT(*) as count FROM bookmarks WHERE user_id = $1",
            to_user_id
        )
        print(f"\nMigration complete!")
        print(f"Total bookmarks for {to_email}: {new_count['count']}")
        print("\nNote: Run the batch job to regenerate clusters.")
        
    finally:
        await db.close_db()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate user data between accounts")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm migration")
    args = parser.parse_args()
    
    # Source and target emails
    FROM_EMAIL = "gp2k@paran.com"
    TO_EMAIL = "gpgp2k@gmail.com"
    
    print("=" * 50)
    print("User Data Migration Script")
    print("=" * 50)
    print(f"From: {FROM_EMAIL}")
    print(f"To:   {TO_EMAIL}")
    print("=" * 50)
    
    asyncio.run(migrate_user_data(FROM_EMAIL, TO_EMAIL, auto_confirm=args.yes))
