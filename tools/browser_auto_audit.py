import asyncio, json, os, time, traceback
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "browser_test_results"
OUT.mkdir(exist_ok=True)
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT = OUT / f"browser_audit_{STAMP}.json"
SCREEN = OUT / f"homepage_{STAMP}.png"

results = {
    "timestamp": datetime.now().isoformat(),
    "checks": [],
    "console_errors": [],
    "page_errors": [],
    "inventory": {},
}

def check(name, passed, detail=""):
    results["checks"].append({
        "name": name, "status": "PASS" if passed else "FAIL",
        "detail": str(detail)
    })
    print(("PASS" if passed else "FAIL") + " | " + name + " | " + str(detail))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})

        page.on("console", lambda msg: results["console_errors"].append(msg.text)
                if msg.type == "error" else None)
        page.on("pageerror", lambda err: results["page_errors"].append(str(err)))

        # Frontend reachability and browser rendering
        try:
            response = await page.goto("http://127.0.0.1:5500/",
                                       wait_until="networkidle", timeout=20000)
            check("Frontend HTTP response", response is not None and response.status == 200,
                  response.status if response else "No response")
            await page.screenshot(path=str(SCREEN), full_page=True)
            check("Homepage rendered", await page.locator("body").count() == 1,
                  await page.title())
        except Exception as e:
            check("Frontend browser launch/navigation", False, repr(e))
            await browser.close()
            return

        # Inspect actual UI controls; do not guess selectors or submit emails.
        results["inventory"] = await page.evaluate("""() => ({
          title: document.title,
          headings: [...document.querySelectorAll('h1,h2,h3')].map(x=>x.innerText.trim()).filter(Boolean),
          forms: [...document.forms].map(f=>({id:f.id, action:f.action, method:f.method})),
          inputs: [...document.querySelectorAll('input')].map(x=>({
            type:x.type, name:x.name, id:x.id, accept:x.accept,
            placeholder:x.placeholder, aria:x.getAttribute('aria-label')
          })),
          textareas: [...document.querySelectorAll('textarea')].map(x=>({
            id:x.id, name:x.name, placeholder:x.placeholder
          })),
          buttons: [...document.querySelectorAll('button,[role=button],input[type=submit]')]
            .map(x=>(x.innerText || x.value || x.getAttribute('aria-label') || '').trim())
            .filter(Boolean),
          links: [...document.querySelectorAll('a')].map(x=>({
            text:x.innerText.trim(), href:x.getAttribute('href')
          })).filter(x=>x.text)
        })""")

        inv = results["inventory"]
        check("UI control inventory collected", True,
              f"{len(inv.get('inputs',[]))} inputs, {len(inv.get('textareas',[]))} textareas, {len(inv.get('buttons',[]))} buttons")

        # Static assets and JavaScript execution
        check("No uncaught browser JavaScript errors",
              len(results["page_errors"]) == 0, results["page_errors"])
        check("No browser console errors",
              len(results["console_errors"]) == 0, results["console_errors"])

        # Backend health
        try:
            api = await page.request.get("http://127.0.0.1:8000/health", timeout=10000)
            body = await api.text()
            check("Backend health endpoint", api.status == 200, body[:500])
        except Exception as e:
            check("Backend health endpoint", False, repr(e))

        # Check documented application routes without mutating data.
        for route in ["/docs", "/openapi.json"]:
            try:
                r = await page.request.get("http://127.0.0.1:8000" + route, timeout=10000)
                check("Backend route " + route, r.status == 200, f"HTTP {r.status}")
                if route == "/openapi.json" and r.status == 200:
                    spec = await r.json()
                    results["api_routes"] = sorted(spec.get("paths", {}).keys())
            except Exception as e:
                check("Backend route " + route, False, repr(e))

        await browser.close()

asyncio.run(main())
results["summary"] = {
    "passed": sum(x["status"] == "PASS" for x in results["checks"]),
    "failed": sum(x["status"] == "FAIL" for x in results["checks"]),
    "total": len(results["checks"])
}
REPORT.write_text(json.dumps(results, indent=2), encoding="utf-8")
print("\n=== AUTOMATED BROWSER AUDIT SUMMARY ===")
print(json.dumps(results["summary"], indent=2))
print("Report:", REPORT)
print("Screenshot:", SCREEN)
