#!/usr/bin/env python3
"""End-to-end smoke test for a running CommercePilot AI instance.

Works against localhost or a deployed URL because the UI and API share one
origin:

    python scripts/verify_deployment.py --base http://127.0.0.1:7860

It creates a disposable example project, runs the full workflow and checks the
artifacts, then deletes the project. Exit code 0 means every check passed.
"""
from __future__ import annotations

import argparse
import re
import sys

import httpx

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "", skip: bool = False) -> None:
    """Record one check and print it as it runs."""
    results.append((SKIP if skip else PASS if ok else FAIL, name, detail))
    print(f"  {results[-1][0]:4}  {name}" + (f"  —  {detail}" if detail else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Origin of the app, no trailing slash")
    parser.add_argument("--timeout", type=float, default=90.0, help="Per-request timeout")
    parser.add_argument("--keep", action="store_true", help="Keep the created test project")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    client = httpx.Client(base_url=base, timeout=args.timeout)
    project_id: str | None = None

    print(f"\nCommercePilot AI smoke test → {base}\n")

    # ---- 1. the interface is served ------------------------------------ #
    try:
        page = client.get("/")
        body = page.text
        check("UI page returns 200", page.status_code == 200, f"HTTP {page.status_code}")
        check(
            "UI page contains the interface",
            "CommercePilot AI" in body and "Product Hunter" in body,
            f"{len(body):,} bytes",
        )
        leaked = re.findall(r"(?:sk-[A-Za-z0-9]{16,}|gsk_[A-Za-z0-9]{20,}|EAAG[A-Za-z0-9]{20,})", body)
        check("UI page exposes no obvious secret", not leaked, f"{len(leaked)} match(es)")
    except Exception as exc:
        check("UI page returns 200", False, str(exc))

    # ---- 2. health ------------------------------------------------------ #
    health: dict = {}
    try:
        response = client.get("/api/health")
        health = response.json() if response.status_code == 200 else {}
        check(
            "Health endpoint reports ok",
            response.status_code == 200 and health.get("status") == "ok",
            f"llm_mode={health.get('llm_mode')}",
        )
        check(
            "AI mode is explicit",
            health.get("llm_mode") in ("llm", "fallback"),
            str(health.get("llm_mode")),
        )
    except Exception as exc:
        check("Health endpoint reports ok", False, str(exc))

    # ---- 3. sample data is labelled ------------------------------------- #
    try:
        payload = client.get("/api/products").json()
        sample_rows = payload.get("products", [])
        check(
            "Sample catalogue is labelled",
            payload.get("is_sample_data") is True
            and "DEMO" in (payload.get("disclaimer") or "")
            and all(row.get("is_sample_data") for row in sample_rows),
            f"{len(sample_rows)} products",
        )
    except Exception as exc:
        check("Sample catalogue is labelled", False, str(exc))

    # ---- 4. create + run a real project --------------------------------- #
    try:
        created = client.post("/api/projects", json={"example": True})
        project_id = created.json().get("id")
        check("Example project created", created.status_code == 201 and bool(project_id), str(project_id))
    except Exception as exc:
        check("Example project created", False, str(exc))

    if project_id:
        try:
            run = client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
            result = run.json()
            statuses = [step["status"] for step in result.get("steps", [])]
            check(
                "Full workflow succeeds",
                run.status_code == 200 and result.get("error") is None and statuses == ["success"] * 7,
                str(statuses),
            )
            project = result.get("project") or {}
            check(
                "Product selected and report built",
                bool(project.get("selected_product")) and bool(project.get("report")),
            )
        except Exception as exc:
            check("Full workflow succeeds", False, str(exc))

        try:
            export = client.get(f"/api/projects/{project_id}/store/export")
            check(
                "Storefront export is real HTML",
                export.status_code == 200
                and "text/html" in export.headers.get("content-type", "")
                and export.text.lstrip().lower().startswith("<!doctype html"),
                f"{len(export.text):,} bytes",
            )
        except Exception as exc:
            check("Storefront export is real HTML", False, str(exc))

        try:
            simulation = client.post(f"/api/projects/{project_id}/campaign/simulate").json()
            check(
                "Campaign simulation is labelled DEMO",
                simulation.get("label") == "DEMO - NOT PUBLISHED",
                str(simulation.get("label")),
            )
        except Exception as exc:
            check("Campaign simulation is labelled DEMO", False, str(exc))

        try:
            reply = client.post(
                f"/api/projects/{project_id}/assistant",
                json={"message": "show me the break-even point"},
            ).json()
            check(
                "Assistant performs the action",
                reply.get("intent") == "analyze" and "break-even" in (reply.get("reply") or "").lower(),
                str(reply.get("intent")),
            )
        except Exception as exc:
            check("Assistant performs the action", False, str(exc))

        if not args.keep:
            try:
                deleted = client.delete(f"/api/projects/{project_id}")
                check("Test project cleaned up", deleted.status_code == 200)
            except Exception as exc:
                check("Test project cleaned up", False, str(exc))

    # ---- summary -------------------------------------------------------- #
    passed = sum(1 for state, _, _ in results if state == PASS)
    failed = sum(1 for state, _, _ in results if state == FAIL)
    skipped = sum(1 for state, _, _ in results if state == SKIP)
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
