"""
Add time_added and read_status fields to bookmarks table.
Usage: python scripts/add_bookmark_fields.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import database as db


async def run_migration():
    """Run the migration to add new bookmark fields."""
    
    print("Connecting to database...")
    await db.init_db()
    
    try:
        # Check current schema
        print("\nChecking current schema...")
        columns = await db.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'bookmarks'
        """)
        existing_columns = [c['column_name'] for c in columns]
        print(f"Existing columns: {existing_columns}")
        
        # Add time_added column if not exists
        if 'time_added' not in existing_columns:
            print("\nAdding time_added column...")
            await db.execute("""
                ALTER TABLE bookmarks 
                ADD COLUMN time_added TIMESTAMPTZ
            """)
            print("  -> time_added column added")
        else:
            print("\ntime_added column already exists, skipping...")
        
        # Add read_status column if not exists
        if 'read_status' not in existing_columns:
            print("\nAdding read_status column...")
            await db.execute("""
                ALTER TABLE bookmarks 
                ADD COLUMN read_status TEXT DEFAULT 'unread'
            """)
            print("  -> read_status column added")
            
            # Add constraint
            print("Adding read_status constraint...")
            try:
                await db.execute("""
                    ALTER TABLE bookmarks
                    ADD CONSTRAINT check_read_status 
                    CHECK (read_status IN ('read', 'unread'))
                """)
                print("  -> Constraint added")
            except Exception as e:
                if 'already exists' in str(e):
                    print("  -> Constraint already exists, skipping...")
                else:
                    raise
        else:
            print("\nread_status column already exists, skipping...")
        
        # Count records to update
        count_result = await db.fetchrow("""
            SELECT COUNT(*) as count 
            FROM bookmarks 
            WHERE time_added IS NULL
        """)
        records_to_update = count_result['count']
        print(f"\nRecords to update: {records_to_update}")
        
        # Migrate existing data
        if records_to_update > 0:
            print("\nMigrating existing data...")
            print("  - Setting time_added to NOW() (UTC)")
            print("  - Setting read_status to 'unread'")
            
            result = await db.execute("""
                UPDATE bookmarks 
                SET time_added = NOW(),
                    read_status = 'unread'
                WHERE time_added IS NULL
            """)
            print(f"  -> Updated: {result}")
        else:
            print("\nNo records to migrate.")
        
        # Create indexes
        print("\nCreating indexes...")
        try:
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_bookmarks_read_status 
                ON bookmarks(user_id, read_status)
            """)
            print("  -> idx_bookmarks_read_status created")
        except Exception as e:
            print(f"  -> idx_bookmarks_read_status: {e}")
        
        try:
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_bookmarks_time_added 
                ON bookmarks(user_id, time_added DESC)
            """)
            print("  -> idx_bookmarks_time_added created")
        except Exception as e:
            print(f"  -> idx_bookmarks_time_added: {e}")
        
        # Verify migration
        print("\nVerifying migration...")
        sample = await db.fetchrow("""
            SELECT id, title, time_added, read_status 
            FROM bookmarks 
            LIMIT 1
        """)
        if sample:
            print(f"Sample record:")
            print(f"  - id: {sample['id']}")
            print(f"  - title: {sample['title'][:50] if sample['title'] else 'N/A'}...")
            print(f"  - time_added: {sample['time_added']}")
            print(f"  - read_status: {sample['read_status']}")
        
        print("\n" + "=" * 50)
        print("Migration completed successfully!")
        print("=" * 50)
        
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(run_migration())
