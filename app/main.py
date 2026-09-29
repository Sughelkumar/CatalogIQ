import uuid
import json
import sqlite3
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, get_db
from app.models import JobCreateInput, ProductUpdateInput, VALID_CATEGORIES
from app.pipeline import metrics, run_job_background

app = FastAPI(title="CatalogIQ")

@app.on_event("startup")
def startup_event():
    init_db()

# Serve Frontend static assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")

# API Endpoints
@app.get("/api/health")
def get_health():
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_concurrency": settings.LLM_CONCURRENCY
    }

@app.get("/api/metrics")
def get_metrics():
    return {
        "llm_calls_total": metrics.llm_calls_total,
        "llm_errors_total": metrics.llm_errors_total,
        "max_concurrent_llm_calls": metrics.max_concurrent_llm_calls
    }

@app.post("/api/jobs", status_code=202)
def create_job(payload: JobCreateInput, background_tasks: BackgroundTasks):
    if not payload.products:
        raise HTTPException(status_code=400, detail={"message": "Product list cannot be empty"})

    for p in payload.products:
        if not p.raw_title or not p.raw_title.strip():
            raise HTTPException(status_code=400, detail={"message": f"Product SKU {p.sku} missing raw_title"})

    job_id = f"j_{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow().isoformat()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO jobs (id, status, total, done, failed, cache_hits, created_at)
    VALUES (?, 'queued', ?, 0, 0, 0, ?)
    """, (job_id, len(payload.products), now))
    conn.commit()
    conn.close()

    products_dict = [p.model_dump() for p in payload.products]
    background_tasks.add_task(run_job_background, job_id, products_dict)

    return {
        "id": job_id,
        "status": "queued",
        "total": len(payload.products),
        "done": 0,
        "failed": 0,
        "cache_hits": 0,
        "created_at": now,
        "started_at": None,
        "finished_at": None
    }

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail={"message": "Job not found"})

    return dict(row)

@app.get("/api/products")
def get_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    q: Optional[str] = None
):
    offset = (page - 1) * page_size
    conn = get_db()
    cursor = conn.cursor()

    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)

    if q:
        conditions.append("(clean_title LIKE ? OR raw_title LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    # Total count query
    cursor.execute(f"SELECT COUNT(*) as cnt FROM products{where_clause}", params)
    total = cursor.fetchone()["cnt"]

    # Items query
    cursor.execute(f"""
        SELECT * FROM products{where_clause}
        ORDER BY sku ASC
        LIMIT ? OFFSET ?
    """, params + [page_size, offset])
    
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        item = dict(r)
        if item["tags"]:
            item["tags"] = json.loads(item["tags"])
        else:
            item["tags"] = []
        items.append(item)

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total
    }

@app.get("/api/products/{sku}")
def get_product(sku: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail={"message": "Product not found"})

    item = dict(row)
    item["tags"] = json.loads(item["tags"]) if item["tags"] else []
    return item

@app.patch("/api/products/{sku}")
def update_product(sku: str, payload: ProductUpdateInput):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail={"message": "Product not found"})

    updates = []
    params = []

    if payload.clean_title is not None:
        if not payload.clean_title.strip():
            conn.close()
            raise HTTPException(status_code=400, detail={"message": "Title cannot be empty"})
        updates.append("clean_title = ?")
        params.append(payload.clean_title.strip())

    if payload.category is not None:
        if payload.category not in VALID_CATEGORIES:
            conn.close()
            raise HTTPException(status_code=400, detail={"message": f"Invalid category: {payload.category}"})
        updates.append("category = ?")
        params.append(payload.category)

    if payload.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps([t.lower() for t in payload.tags[:5]]))

    updates.append("status = 'approved'")
    params.append(sku)

    cursor.execute(f"UPDATE products SET {', '.join(updates)} WHERE sku = ?", params)
    conn.commit()

    cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
    updated_row = dict(cursor.fetchone())
    conn.close()

    updated_row["tags"] = json.loads(updated_row["tags"]) if updated_row["tags"] else []
    return updated_row