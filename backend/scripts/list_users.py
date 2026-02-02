"""List all user accounts."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import database as db

async def list_users():
    await db.init_db()
    try:
        users = await db.fetch('''
            SELECT id, email, created_at, last_sign_in_at
            FROM auth.users
            ORDER BY created_at DESC
        ''')
        
        # Also get bookmark counts per user
        bookmark_counts = await db.fetch('''
            SELECT user_id, COUNT(*) as count
            FROM bookmarks
            GROUP BY user_id
        ''')
        counts_map = {str(r['user_id']): r['count'] for r in bookmark_counts}
        
        print(f"Total users: {len(users)}")
        print("=" * 80)
        for u in users:
            user_id = str(u['id'])
            bookmark_count = counts_map.get(user_id, 0)
            print(f"Email: {u['email']}")
            print(f"  ID: {user_id}")
            print(f"  Bookmarks: {bookmark_count}")
            print(f"  Created: {u['created_at']}")
            print(f"  Last login: {u['last_sign_in_at']}")
            print()
    finally:
        await db.close_db()

if __name__ == "__main__":
    asyncio.run(list_users())
