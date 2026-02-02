"""
Import bookmarks from Pocket CSV export.
Usage: python scripts/import_pocket_csv.py <csv_file>
"""
import asyncio
import csv
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import database as db


async def get_user_id_by_email(email: str) -> str | None:
    """Get user_id from Supabase auth.users by email."""
    row = await db.fetchrow(
        "SELECT id FROM auth.users WHERE email = $1",
        email
    )
    return str(row["id"]) if row else None


async def import_pocket_csv(csv_path: str, user_email: str):
    """Import bookmarks from Pocket CSV export."""
    
    print(f"Reading CSV file: {csv_path}")
    
    # Read CSV file
    bookmarks = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bookmarks.append(row)
    
    print(f"Found {len(bookmarks)} bookmarks in CSV")
    
    # Connect to database
    print("\nConnecting to database...")
    await db.init_db()
    
    try:
        # Get user ID
        print(f"Finding user ID for {user_email}...")
        user_id = await get_user_id_by_email(user_email)
        if not user_id:
            print(f"ERROR: User {user_email} not found!")
            return
        print(f"  -> {user_id}")
        
        # Check existing bookmarks
        existing = await db.fetch(
            "SELECT url FROM bookmarks WHERE user_id = $1",
            user_id
        )
        existing_urls = set(r['url'] for r in existing)
        print(f"Existing bookmarks: {len(existing_urls)}")
        
        # Filter out duplicates
        new_bookmarks = [b for b in bookmarks if b['url'] not in existing_urls]
        print(f"New bookmarks to import: {len(new_bookmarks)}")
        
        if len(new_bookmarks) == 0:
            print("No new bookmarks to import!")
            return
        
        # Import bookmarks
        print("\nImporting bookmarks...")
        imported = 0
        failed = 0
        
        for i, bookmark in enumerate(new_bookmarks):
            try:
                # Convert Unix timestamp to datetime
                time_added = None
                if bookmark.get('time_added'):
                    try:
                        ts = int(bookmark['time_added'])
                        time_added = datetime.fromtimestamp(ts, tz=timezone.utc)
                    except (ValueError, OSError):
                        time_added = datetime.now(tz=timezone.utc)
                else:
                    time_added = datetime.now(tz=timezone.utc)
                
                # Parse tags (comma-separated)
                tags = []
                if bookmark.get('tags'):
                    tags = [t.strip() for t in bookmark['tags'].split(',') if t.strip()]
                
                # Parse read status
                read_status = 'unread'
                if bookmark.get('status', '').lower() == 'read':
                    read_status = 'read'
                
                # Insert bookmark
                await db.execute(
                    """
                    INSERT INTO bookmarks (user_id, url, title, tags, time_added, read_status, status, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, 'pending_embedding', NOW())
                    ON CONFLICT (user_id, url) DO NOTHING
                    """,
                    user_id,
                    bookmark['url'],
                    bookmark.get('title', ''),
                    tags,
                    time_added,
                    read_status
                )
                imported += 1
                
                # Progress indicator
                if (i + 1) % 100 == 0:
                    print(f"  Progress: {i + 1}/{len(new_bookmarks)}")
                    
            except Exception as e:
                failed += 1
                print(f"  Failed: {bookmark.get('url', 'unknown')[:50]}... - {e}")
        
        print(f"\nImport completed!")
        print(f"  - Imported: {imported}")
        print(f"  - Failed: {failed}")
        print(f"  - Skipped (duplicates): {len(bookmarks) - len(new_bookmarks)}")
        
        # Verify total
        total = await db.fetchrow(
            "SELECT COUNT(*) as count FROM bookmarks WHERE user_id = $1",
            user_id
        )
        print(f"\nTotal bookmarks for {user_email}: {total['count']}")
        
    finally:
        await db.close_db()


if __name__ == "__main__":
    # Default values
    CSV_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "part_000000.csv"
    )
    USER_EMAIL = "gpgp2k@gmail.com"
    
    # Override with command line args if provided
    if len(sys.argv) > 1:
        CSV_PATH = sys.argv[1]
    if len(sys.argv) > 2:
        USER_EMAIL = sys.argv[2]
    
    print("=" * 60)
    print("Pocket CSV Import")
    print("=" * 60)
    print(f"CSV File: {CSV_PATH}")
    print(f"User: {USER_EMAIL}")
    print("=" * 60)
    
    asyncio.run(import_pocket_csv(CSV_PATH, USER_EMAIL))
