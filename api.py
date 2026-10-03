# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "beautifulsoup4",
#     "fastapi",
#     "httpx",
#     "uvicorn",
# ]
# ///
"""FastAPI Microservice for n8n Integration.

Allows n8n (or any webhook system) to scrape single or bulk websites
via HTTP POST and receive instant structured JSON responses.

Run with:
    uv run api.py
Access API docs at:
    http://localhost:8000/docs
"""

import sys
from typing import List, Optional
from urllib.parse import urlparse

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import httpx

# Import scraping logic from full_extractor
from full_extractor import scrape_full_site, asyncio

app = FastAPI(
    title="n8n Lead & Website Scraper Service",
    description="Microservice to extract emails, socials, and full metadata for n8n workflows.",
    version="1.0.0",
)


class ScrapeRequest(BaseModel):
    url: Optional[str] = None
    urls: Optional[List[str]] = None
    timeout: float = 15.0


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "n8n Lead Scraper API",
        "docs": "http://localhost:8000/docs",
    }


@app.post("/scrape")
async def scrape_endpoint(req: ScrapeRequest):
    target_urls = []
    if req.url:
        target_urls.append(req.url)
    if req.urls:
        target_urls.extend(req.urls)

    if not target_urls:
        raise HTTPException(status_code=400, detail="Must provide 'url' or 'urls'")

    # Deduplicate
    unique_urls = list(dict.fromkeys(target_urls))
    semaphore = asyncio.Semaphore(10)

    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    async with httpx.AsyncClient(
        timeout=req.timeout,
        verify=False,
        limits=limits,
    ) as client:
        tasks = [scrape_full_site(client, u, semaphore) for u in unique_urls]
        results = await asyncio.gather(*tasks)

    # If single URL requested, return single object for easier n8n mapping
    if req.url and not req.urls:
        return results[0]

    return {"count": len(results), "results": results}


if __name__ == "__main__":
    print("\n[+] Starting n8n Scraper API on http://0.0.0.0:8000 ...")
    print("[+] Test the API in your browser: http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
