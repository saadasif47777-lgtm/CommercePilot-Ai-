#!/usr/bin/env python3
"""Deployment smoke test for CommercePilot AI.

Run it against any environment (local or deployed):

    python scripts/verify_deployment.py \
        --backend https://commercepilot-ai-api.onrender.com \
        --frontend https://commercepilot-ai.vercel.app

It checks the exact acceptance criteria used for judging:
health endpoint, CORS, sample-data labelling, Example Project ->
Run Full Commerce Workflow -> report -> assistant, and that the
frontend bundle contains no secrets or localhost URLs.
Exit code 0 = every check passed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

import httpx

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "", skip: bool = False) -> None:
    results.append((SKIP if skip else PASS if ok else FAIL, name, detail))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", required=True, help="Backend origin, no trailing slash")
    ap.add_argument("--frontend", default="", help="Frontend origin (optional)")
    ap.add_argument("--origin", default="", help="Origin for CORS checks (default: frontend)")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--keep", action="store_true", help="Keep the created test project")
    args = ap.parse_args()

    backend = args.backend.rstrip("/")
    frontend = args.frontend.rstrip("/")
    origin = args.origin or frontend
    client = httpx.Client(base_url=backend, timeout=args.timeout,
                          headers={"Origin": origin} if origin else {})

    # 1. Health, independently of the frontend ------------------------------
    try:
        r = client.get("/api/health")
        body = r.json() if r.status_code == 200 else {}
        check("Backend health endpoint returns 200 JSON",
              r.status_code == 200 and body.get("status") == "ok",
              f"HTTP {r.status_code} {json.dumps(body)[:160]}")
        check("Health reports llm_mode (fallback is expected without keys)",
              "llm_mode" in body, str(body.get("llm_mode")))
    except Exception as exc:  # noqa: BLE001
        check("Backend health endpoint returns 200 JSON", False, str(exc))

    # 2. CORS ---------------------------------------------------------------
    if origin:
        try:
            r = client.get("/api/health")
            acao = r.headers.get("access-control-allow-origin", "")
            check(f"CORS allows {origin}", acao == origin, f"ACAO={acao!r}")
            r = client.request("OPTIONS", "/api/projects",
                               headers={"Origin": origin,
                                        "Access-Control-Request-Method": "POST",
                                        "Access-Control-Request-Headers": "content-type"})
            check("CORS preflight for POST succeeds",
                  r.status_code in (200, 204) and
                  r.headers.get("access-control-allow-origin") == origin,
                  f"HTTP {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            check("CORS allows " + origin, False, str(exc))
    else:
        check("CORS allows <frontend origin>", False, "no --frontend/--origin given", skip=True)

    # 3. Sample data labelling ---------------------------------------------
    try:
        r = client.get("/api/products")
        data = r.json()
        products = data.get("products", [])
        check("Sample catalogue returns products",
              r.status_code == 200 and len(products) > 0, f"count={data.get('count')}")
        check("Sample data is explicitly labelled as demo",
              bool(data.get("is_sample_data")) and "DEMO" in str(data.get("disclaimer", "")).upper(),
              str(data.get("disclaimer"))[:100])
    except Exception as exc:  # noqa: BLE001
        check("Sample catalogue returns products", False, str(exc))

    # 4. Example Project -> full workflow ----------------------------------
    project_id = ""
    try:
        r = client.post("/api/projects", json={"example": True})
        project_id = (r.json() or {}).get("id", "")
        check("Example Project created (201)", r.status_code == 201 and bool(project_id),
              f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        check("Example Project created (201)", False, str(exc))

    if project_id:
        try:
            started = time.time()
            r = client.post(f"/api/projects/{project_id}/run-workflow",
                            json={"auto_select": True, "mode": "sample"})
            wf = r.json() if r.status_code == 200 else {}
            steps = wf.get("steps") or []
            statuses = [s.get("status") for s in steps] if isinstance(steps, list) else []
            ok = (r.status_code == 200 and not wf.get("error")
                  and bool(steps) and all(st == "success" for st in statuses))
            check("Run Full Commerce Workflow completes", ok,
                  f"HTTP {r.status_code} error={wf.get('error')} in "
                  f"{time.time()-started:.1f}s steps={statuses}")
        except Exception as exc:  # noqa: BLE001
            check("Run Full Commerce Workflow completes", False, str(exc))

        for name, method, path, payload in [
            ("Report generated", "GET", f"/api/projects/{project_id}/report", None),
            ("Selected product passed to storefront", "GET", f"/api/projects/{project_id}", None),
            ("Assistant answers with project context", "POST",
             f"/api/projects/{project_id}/assistant", {"message": "What is my budget?"}),
        ]:
            try:
                r = client.request(method, path, json=payload)
                ok = r.status_code == 200
                detail = f"HTTP {r.status_code}"
                if ok and name.startswith("Selected"):
                    proj = r.json()
                    ok = bool(proj.get("selected_product")) and bool(proj.get("store_spec"))
                    detail += f" product={bool(proj.get('selected_product'))} store={bool(proj.get('store_spec'))}"
                if ok and name.startswith("Assistant"):
                    ok = bool(r.json().get("reply"))
                    detail += f" reply_len={len(str(r.json().get('reply')))}"
                check(name, ok, detail)
            except Exception as exc:  # noqa: BLE001
                check(name, False, str(exc))

        if not args.keep:
            try:
                client.delete(f"/api/projects/{project_id}")
            except Exception:  # noqa: BLE001
                pass

    # 5. Frontend -----------------------------------------------------------
    if frontend:
        try:
            with httpx.Client(timeout=args.timeout, follow_redirects=True) as fc:
                r = fc.get(frontend)
                html = r.text
                check("Frontend serves the app HTML",
                      r.status_code == 200 and "<div id=\"root\"" in html,
                      f"HTTP {r.status_code} {r.headers.get('content-type')}")
                r = fc.get(frontend + "/assets")
                assets = re.findall(r"src=\"(/assets/[^\"]+\.js)\"", html) or []
                bundle = ""
                if assets:
                    b = fc.get(frontend + assets[0])
                    bundle = b.text
                # Dev servers have no built bundle (they serve modules on demand);
                # fall back to the HTML so the check is never vacuous.
                scan_target = bundle or html
                check("JS bundle contains no secrets",
                      not re.search(r"OPENAI_API_KEY|sk-[A-Za-z0-9]{20,}|EAAG\w+|shpat_\w+", scan_target),
                      f"scanned {len(scan_target)} chars"
                      + ("" if bundle else " (dev server: index.html only)"))
                # The configured API base is allowed (it is deployment config);
                # any OTHER localhost/127.0.0.1 URL would be a leftover dev default.
                base_host = backend.split("//")[-1]
                scan = scan_target.replace(base_host, "")
                stray = re.search(r"(localhost|127\.0\.0\.1):\d+", scan)
                check("JS bundle contains no stray localhost/127.0.0.1 URLs",
                      stray is None, "clean" if stray is None else f"found {stray.group(0)}")
                is_dev_server = "/@vite/client" in html
                if backend:
                    inlined = backend.split("//")[-1] in bundle
                    check("JS bundle points at the deployed backend", inlined or is_dev_server,
                          "base URL inlined" if inlined else
                          ("dev server (same-origin proxy - expected)" if is_dev_server
                           else "VITE_API_BASE_URL missing from this build"),
                          skip=(is_dev_server and not inlined))
                r = fc.get(frontend + "/store")
                check("Client-side deep link /store returns the app (SPA fallback)",
                      r.status_code == 200 and "<div id=\"root\"" in r.text, f"HTTP {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            check("Frontend serves the app HTML", False, str(exc))
    else:
        check("Frontend checks", False, "--frontend not provided", skip=True)

    # Report ----------------------------------------------------------------
    width = max(len(n) for _, n, _ in results) if results else 0
    failed = 0
    for status, name, detail in results:
        if status == FAIL:
            failed += 1
        print(f"[{status}] {name.ljust(width)}  {detail}")
    print(f"\n{len(results) - failed}/{len(results)} checks passed"
          + (f", {failed} FAILED" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
