"""Exercise the deployed entry point with runtime dependencies only.

Run as `python -m scripts.check_serverless_startup` in an isolated environment.
CI supplies a disposable PostgreSQL database and a nonfunctional AI test key;
these checks never contact AI, Shopify or Meta and never use production data.
"""
import os

from fastapi.testclient import TestClient

from api.index import app
from commercepilot.ai.prompts import load_prompt


def main():
    if not os.environ.get("TEST_DATABASE_URL"):
        raise RuntimeError("Set TEST_DATABASE_URL to a disposable test database")
    if os.environ.get("DATABASE_URL") != os.environ["TEST_DATABASE_URL"]:
        raise RuntimeError("DATABASE_URL must match the disposable TEST_DATABASE_URL")

    # TestClient's context manager runs real startup/lifespan validation.
    with TestClient(app) as client:
        for path in ("/api/health", "/api/projects", "/api/integrations/status"):
            response = client.get(path)
            if response.status_code != 200:
                raise RuntimeError(f"{path} returned {response.status_code}")
            response.json()
            print(f"PASS GET {path}")
        response = client.post("/api/advisor/session", json={})
        if response.status_code != 200 or not response.json().get("session_token"):
            raise RuntimeError(f"Advisor session failed ({response.status_code})")
        print("PASS POST /api/advisor/session")
        for name in ("advisor_plan", "advisor_answer"):
            load_prompt(name)
        print("PASS packaged advisor prompts")


if __name__ == "__main__":
    main()
