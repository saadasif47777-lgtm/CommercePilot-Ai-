#!/usr/bin/env python3
"""Read-only deployment checks; --live-model explicitly permits a small AI call."""
import argparse
import os

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--live-model", action="store_true")
    args = parser.parse_args()
    failures = []
    with httpx.Client(base_url=args.base.rstrip("/"), timeout=120) as client:
        def check(name, valid):
            print(f"{'PASS' if valid else 'FAIL'} {name}")
            if not valid:
                failures.append(name)
        health = client.get("/api/health")
        check("health", health.status_code == 200)
        check("production mode", health.json().get("mode") == "production")
        check("unauthenticated access rejected", client.get("/api/projects").status_code == 401)
        client.auth = (os.environ.get("ADMIN_USERNAME", "admin"), os.environ.get("ADMIN_PASSWORD", ""))
        check("authenticated database read", client.get("/api/projects").status_code == 200)
        check("sample catalogue disabled", client.get("/api/products").status_code == 404)
        if args.live_model:
            response = client.post("/api/integrations/llm/verify")
            check("live model response", response.status_code == 200 and response.json().get("verified") is True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
