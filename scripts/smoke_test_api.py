#!/usr/bin/env python3
"""Smoke test the running API."""
import sys
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"

def check(label: str, r: httpx.Response) -> None:
    status = "OK" if r.status_code == 200 else "FAIL"
    print(f"[{status}] {label}: {r.status_code}")
    if r.status_code != 200:
        print("  ", r.text[:200])

r = httpx.get(f"{BASE}/healthz")
check("GET /healthz", r)

r = httpx.get(f"{BASE}/metadata")
check("GET /metadata", r)

r = httpx.get(f"{BASE}/search", params={"q": "カフェ", "bbox": "139.55,35.50,139.95,35.85"})
check("GET /search?q=カフェ&bbox=...", r)
if r.status_code == 200:
    data = r.json()
    print(f"  count={data.get('count')}")

r = httpx.get(f"{BASE}/nearby", params={"q": "コンビニ", "lat": 35.681, "lon": 139.767, "radius_m": 500})
check("GET /nearby?q=コンビニ&...", r)
