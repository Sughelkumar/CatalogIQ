import sqlite3
import json
import asyncio
from typing import Optional, Dict, Any, List, Tuple

DB_PATH = "catalogiq.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        raw_title TEXT NOT NULL,
        raw_description TEXT,
        clean_title TEXT,
        category TEXT,
        brand TEXT,
        tags TEXT,
        status TEXT NOT NULL,
        error TEXT
    )
    """)
    
    # Jobs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        total INTEGER NOT NULL,
        done INTEGER NOT NULL,
        failed INTEGER NOT NULL,
        cache_hits INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT
    )
    """)
    
    # Persistent Enrichment Cache Table (by content hash)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS enrichment_cache (
        content_hash TEXT PRIMARY KEY,
        enrichment_json TEXT NOT NULL
    )
    """)
    
    conn.commit()
    conn.close()

# Async wrappers over synchronous SQLite
async def db_get_cache(content_hash: str) -> Optional[Dict[str, Any]]:
    def _op():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT enrichment_json FROM enrichment_cache WHERE content_hash = ?", (content_hash,))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row["enrichment_json"]) if row else None
    return await asyncio.to_thread(_op)

async def db_save_cache(content_hash: str, enrichment_data: Dict[str, Any]):
    def _op():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO enrichment_cache (content_hash, enrichment_json) VALUES (?, ?)",
            (content_hash, json.dumps(enrichment_data))
        )
        conn.commit()
        conn.close()
    await asyncio.to_thread(_op)

async def db_save_product(product_data: Dict[str, Any]):
    def _op():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO products (sku, raw_title, raw_description, clean_title, category, brand, tags, status, error)
        VALUES (:sku, :raw_title, :raw_description, :clean_title, :category, :brand, :tags, :status, :error)
        ON CONFLICT(sku) DO UPDATE SET
            raw_title=excluded.raw_title,
            raw_description=excluded.raw_description,
            clean_title=excluded.clean_title,
            category=excluded.category,
            brand=excluded.brand,
            tags=excluded.tags,
            status=excluded.status,
            error=excluded.error
        """, {
            "sku": product_data["sku"],
            "raw_title": product_data["raw_title"],
            "raw_description": product_data.get("raw_description"),
            "clean_title": product_data.get("clean_title"),
            "category": product_data.get("category"),
            "brand": product_data.get("brand"),
            "tags": json.dumps(product_data.get("tags")) if product_data.get("tags") is not None else None,
            "status": product_data["status"],
            "error": product_data.get("error")
        })
        conn.commit()
        conn.close()
    await asyncio.to_thread(_op)