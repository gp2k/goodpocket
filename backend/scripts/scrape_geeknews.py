"""
Scrape GeekNews (news.hada.io) articles and add to bookmarks.
Run from backend directory: python scripts/scrape_geeknews.py
"""
import asyncio
import httpx
from uuid import UUID
from typing import List, Dict, Any
import re
import time

import asyncpg
from pgvector.asyncpg import register_vector

# Load environment
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# GeekNews URLs
GEEKNEWS_API = "https://api.hada.io"
GEEKNEWS_RSS = "https://news.hada.io/rss/"

# Headers to avoid blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


async def fetch_geeknews_articles(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch articles from GeekNews by scraping the website.
    """
    articles = []
    page = 1
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        while len(articles) < limit:
            print(f"Fetching page {page}...")
            
            # GeekNews main page with pagination
            if page == 1:
                url = "https://news.hada.io/"
            else:
                url = f"https://news.hada.io/?page={page}"
            
            try:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                
                
                import re
                
                # GeekNews HTML structure:
                # <div class='topictitle'><a href='URL'><h1>Title</h1></a>
                # Pattern: extract href and h1 content from topictitle div
                pattern = r"<div class=topictitle><a href='([^']+)'[^>]*><h1>([^<]+)</h1></a>"
                matches = re.findall(pattern, html)
                
                if matches:
                    print(f"  Found {len(matches)} articles")
                
                if not matches:
                    print(f"  No articles found on page {page}")
                    break
                
                for href, title in matches:
                    if len(articles) >= limit:
                        break
                    
                    # Make URL absolute
                    if href.startswith("/"):
                        url = f"https://news.hada.io{href}"
                    else:
                        url = href
                    
                    title = title.strip()
                    
                    if url and title:
                        articles.append({
                            "url": url,
                            "title": title,
                            "summary": "",
                        })
                        # Use safe printing for Windows
                        try:
                            print(f"  [{len(articles)}] {title[:50]}...")
                        except UnicodeEncodeError:
                            print(f"  [{len(articles)}] (title contains special chars)")
                
                page += 1
                await asyncio.sleep(1)  # Rate limiting - be nice to the server
                
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break
    
    # If scraping doesn't work, try RSS as fallback
    if len(articles) < 10:
        print("Trying RSS feed as fallback...")
        articles = await fetch_from_rss(limit)
    
    return articles


async def fetch_from_rss(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch from GeekNews RSS feed as fallback."""
    import xml.etree.ElementTree as ET
    
    articles = []
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        try:
            # GeekNews RSS feed
            response = await client.get(GEEKNEWS_RSS)
            response.raise_for_status()
            
            root = ET.fromstring(response.text)
            
            for item in root.findall(".//item"):
                if len(articles) >= limit:
                    break
                
                title = item.find("title")
                link = item.find("link")
                description = item.find("description")
                
                if title is not None and link is not None:
                    article = {
                        "url": link.text,
                        "title": title.text,
                        "summary": description.text if description is not None else "",
                    }
                    articles.append(article)
                    print(f"  [{len(articles)}] {article['title'][:50]}...")
                    
        except Exception as e:
            print(f"RSS fetch error: {e}")
    
    return articles


async def get_user_id(conn: asyncpg.Connection) -> UUID:
    """Get the first user ID from the database."""
    row = await conn.fetchrow("SELECT id FROM auth.users LIMIT 1")
    if row:
        return row["id"]
    raise ValueError("No users found in database")


async def insert_bookmarks(articles: List[Dict[str, Any]], user_id: UUID):
    """Insert articles as bookmarks."""
    # Import tag generator
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.services.tag_generator import generate_tags
    
    conn = await asyncpg.connect(DATABASE_URL)
    await register_vector(conn)
    
    inserted = 0
    skipped = 0
    failed = 0
    
    try:
        for article in articles:
            url = article["url"]
            title = article["title"]
            summary = article.get("summary", "")
            
            # Check for duplicate
            existing = await conn.fetchrow(
                "SELECT id FROM bookmarks WHERE user_id = $1 AND url = $2",
                user_id, url
            )
            
            if existing:
                try:
                    print(f"  Skipped (duplicate): {title[:40]}...")
                except UnicodeEncodeError:
                    print(f"  Skipped (duplicate): [special chars]")
                skipped += 1
                continue
            
            try:
                # Generate tags
                tags = generate_tags(title=title, text=summary)
                
                # Insert bookmark
                await conn.execute(
                    """
                    INSERT INTO bookmarks (
                        user_id, url, title, summary, tags, status
                    )
                    VALUES ($1, $2, $3, $4, $5, 'pending_embedding')
                    """,
                    user_id,
                    url,
                    title,
                    summary[:2000] if summary else None,
                    tags,
                )
                
                inserted += 1
                try:
                    print(f"  Inserted [{inserted}]: {title[:40]}... (tags: {tags[:3]})")
                except UnicodeEncodeError:
                    print(f"  Inserted [{inserted}]: [special chars] (tags: {len(tags)})")
                
            except Exception as e:
                try:
                    print(f"  Failed: {title[:40]}... - {e}")
                except UnicodeEncodeError:
                    print(f"  Failed: [special chars] - {e}")
                failed += 1
                
    finally:
        await conn.close()
    
    return {"inserted": inserted, "skipped": skipped, "failed": failed}


async def main():
    print("=" * 60)
    print("GeekNews Scraper for GoodPocket")
    print("=" * 60)
    
    # Fetch articles
    print("\nFetching articles from GeekNews...")
    articles = await fetch_geeknews_articles(limit=100)
    print(f"\nFetched {len(articles)} articles")
    
    if not articles:
        print("No articles to import")
        return
    
    # Get user ID
    print("\nConnecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        user_id = await get_user_id(conn)
        print(f"Using user ID: {user_id}")
    finally:
        await conn.close()
    
    # Insert bookmarks
    print("\nInserting bookmarks...")
    result = await insert_bookmarks(articles, user_id)
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Inserted: {result['inserted']}")
    print(f"  Skipped (duplicates): {result['skipped']}")
    print(f"  Failed: {result['failed']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
