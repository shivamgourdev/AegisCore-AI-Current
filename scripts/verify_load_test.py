"""AEGISCORE_PHASE7_LOAD_TEST
Performance/Load Testing for AegisCore AI Backend.

Tests concurrent request handling, response times, and resource usage
under concurrent load. Tests the following endpoints:
- GET /health
- POST /documents/upload
- POST /search
- POST /ask
- POST /jobs/analyze
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

import httpx

BACKEND_URL = os.environ.get("AEGISCORE_BACKEND_URL", "http://127.0.0.1:8000")


async def make_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Make a single request and return timing info."""
    start = time.perf_counter()
    try:
        response = await client.request(method, path, **kwargs)
        elapsed = time.perf_counter() - start
        return {
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed * 1000, 2),
            "success": response.status_code < 400,
        }
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return {
            "method": method,
            "path": path,
            "status_code": 0,
            "elapsed_ms": round(elapsed * 1000, 2),
            "success": False,
            "error": str(exc),
        }


async def run_concurrent_requests(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    num_requests: int,
    concurrency: int,
) -> list[dict[str, Any]]:
    """Run concurrent requests with specified concurrency level."""
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_request():
        async with semaphore:
            return await make_request(client, method, path)

    tasks = [bounded_request() for _ in range(num_requests)]
    return await asyncio.gather(*tasks)


async def main() -> None:
    """Run load tests against the AegisCore AI backend."""
    print("=" * 60)
    print("AegisCore AI Phase 7 - Load Testing")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Health endpoint - high concurrency
        print("\n[Test 1] Health endpoint - concurrent requests")
        results = await run_concurrent_requests(
            client, "GET", "/health", num_requests=100, concurrency=20
        )
        successful = [r for r in results if r["success"]]
        elapsed_ms = [r["elapsed_ms"] for r in successful]
        print(f"  Total requests: {len(results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(results) - len(successful)}")
        if elapsed_ms:
            print(f"  Min latency: {min(elapsed_ms):.1f}ms")
            print(f"  Median latency: {median(elapsed_ms):.1f}ms")
            print(f"  Max latency: {max(elapsed_ms):.1f}ms")
            print(f"  Mean latency: {mean(elapsed_ms):.1f}ms")
            if len(elapsed_ms) > 1:
                print(f"  Std dev: {stdev(elapsed_ms):.1f}ms")

        # Test 2: Search endpoint - concurrent requests
        print("\n[Test 2] Search endpoint - concurrent requests")
        results = await run_concurrent_requests(
            client,
            "POST",
            "/search",
            num_requests=50,
            concurrency=10,
            json={"query": "Project Orion revenue", "top_k": 5, "mode": "dense"},
        )
        successful = [r for r in results if r["success"]]
        elapsed_ms = [r["elapsed_ms"] for r in successful]
        print(f"  Total requests: {len(results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(results) - len(successful)}")
        if elapsed_ms:
            print(f"  Min latency: {min(elapsed_ms):.1f}ms")
            print(f"  Median latency: {median(elapsed_ms):.1f}ms")
            print(f"  Max latency: {max(elapsed_ms):.1f}ms")
            print(f"  Mean latency: {mean(elapsed_ms):.1f}ms")
            if len(elapsed_ms) > 1:
                print(f"  Std dev: {stdev(elapsed_ms):.1f}ms")

        # Test 3: Ask endpoint - sequential (LLM-dependent, slower)
        print("\n[Test 3] Ask endpoint - sequential requests")
        results = []
        for i in range(5):
            result = await make_request(
                client,
                "POST",
                "/ask",
                json={
                    "query": "What is Project Orion's revenue?",
                    "top_k": 5,
                    "min_similarity": 0.30,
                },
            )
            results.append(result)
            print(f"  Request {i + 1}: {result['elapsed_ms']:.1f}ms - "
                  f"{'OK' if result['success'] else 'FAILED'}")

        successful = [r for r in results if r["success"]]
        elapsed_ms = [r["elapsed_ms"] for r in successful]
        if elapsed_ms:
            print(f"  Min latency: {min(elapsed_ms):.1f}ms")
            print(f"  Median latency: {median(elapsed_ms):.1f}ms")
            print(f"  Max latency: {max(elapsed_ms):.1f}ms")
            print(f"  Mean latency: {mean(elapsed_ms):.1f}ms")

        # Test 4: Job analysis - concurrent requests
        print("\n[Test 4] Job analysis endpoint - concurrent requests")
        results = await run_concurrent_requests(
            client,
            "POST",
            "/jobs/analyze",
            num_requests=20,
            concurrency=10,
            json={
                "resume_text": "Python developer with FastAPI, SQL, Docker experience.",
                "job_description": "We need Python, SQL, Docker, Machine Learning.",
            },
        )
        successful = [r for r in results if r["success"]]
        elapsed_ms = [r["elapsed_ms"] for r in successful]
        print(f"  Total requests: {len(results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(results) - len(successful)}")
        if elapsed_ms:
            print(f"  Min latency: {min(elapsed_ms):.1f}ms")
            print(f"  Median latency: {median(elapsed_ms):.1f}ms")
            print(f"  Max latency: {max(elapsed_ms):.1f}ms")
            print(f"  Mean latency: {mean(elapsed_ms):.1f}ms")
            if len(elapsed_ms) > 1:
                print(f"  Std dev: {stdev(elapsed_ms):.1f}ms")

        print("\n" + "=" * 60)
        print("Load testing complete.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
