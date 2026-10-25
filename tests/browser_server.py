"""Local browser-test server. Test-only provider transports never leave this process."""
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import uvicorn


def main():
    with TemporaryDirectory(prefix="browser-test-", dir=Path(__file__).resolve().parents[1]) as directory:
        os.environ.update(APP_MODE="production", DB_PATH=f"{directory}/test.sqlite3", SECRETS_DIR=f"{directory}/secrets",
                          DATABASE_URL="",
                          LLM_API_KEY="browser-test-key-not-real", LLM_MODEL="test-model",
                          PUBLIC_URL="http://127.0.0.1:8011", CORS_ORIGINS="http://127.0.0.1:8011")
        from app import app
        from commercepilot import integrations
        from commercepilot.agents import product_hunter
        from commercepilot.ai import client as ai_client
        from commercepilot.tools import product_pages
        from commercepilot.tools.product_pages import PageFacts
        from commercepilot.tools.web_search import SearchOutcome, SearchResult
        from tests.test_support import catalog, product, shop_data
        product_hunter.inspect_pages = lambda urls: [PageFacts(kind="product", title="Desk lamp PKR 2000", price=2000, currency="PKR", price_basis="product structured offer", url=url) for url in urls]
        product_pages.inspect_page = lambda url: PageFacts(kind="product", title="Imported URL lamp", price=3000, currency="PKR", price_basis="product structured offer", availability="InStock", url=url)

        def model(url, headers, payload, timeout):
            system = payload["messages"][0]["content"]
            user = payload["messages"][1]["content"]
            if "You interpret a CommercePilot" in system:
                conversation = json.loads(re.search(r"<untrusted_conversation>\n(.*?)\n</untrusted_conversation>", user, re.S)[1])
                message = conversation["message"].casefold()
                if "report" in message:
                    data = {"intent": "action", "requested_action": "report"}
                elif "50k" in message:
                    data = {"intent": "budget", "updates": {"budget": 50000, "currency": "PKR", "budget_scope": "business", "niche": "skincare", "location": "Lahore"},
                            "evidence": {"budget": "50k", "currency": "PKR", "budget_scope": "whole business", "niche": "skincare", "location": "Lahore"}}
                else:
                    data = {"intent": "guidance"}
            elif "CommercePilot's friendly AI business guide" in system:
                context = json.loads(re.search(r"<untrusted_context>\n(.*?)\n</untrusted_context>", user, re.S)[1])
                profile = context["profile"]
                data = {"reply": "Welcome! I can guide your business setup, review your idea and help prepare a sensible budget. Marketing Studio creates campaign drafts for your review; it does not publish or spend money.",
                        "next_steps": [{"title": "Save your business details", "explanation": "Enter your niche, location and audience.", "route": "/business"}],
                        "questions": ["Who is your target customer?"]}
                if profile.get("niche"):
                    data.update(reply=f"For {profile['niche']} in {profile.get('location') or 'your market'}, validate the offer and costs before a small ad test. Use the calculated budget to keep a reserve.",
                                strengths=["A focused niche can make your first creative test more specific."],
                                risks=[{"factor": "Delivery and returns", "explanation": "Local fulfilment and returns can reduce the margin.", "mitigation": "Get courier quotes and include fees and return costs before advertising."}],
                                next_steps=[{"title": "Prepare a campaign draft", "explanation": "Review the budget, then prepare creative tests in Marketing Studio.", "route": "/marketing"}])
            elif "You interpret a shopper" in system:
                conversation = json.loads(re.search(r"<untrusted_conversation>\n(.*?)\n</untrusted_conversation>", user, re.S)[1])
                message = conversation["message"].casefold()
                if "order" in message:
                    data = {"intent": "handoff"}
                else:
                    data = {"intent": "policies", "terms": ["returns"]} if "return policy" in message else {"intent": "products", "terms": ["lamp"], "max_price": 25}
            elif "friendly customer support assistant" in system:
                context = json.loads(re.search(r"<untrusted_knowledge>\n(.*?)\n</untrusted_knowledge>", user, re.S)[1])
                if context["products"]:
                    data = {"answer": "This desk lamp fits your budget. Check the product page for current price and availability.", "product_ids": [context["products"][0]["id"]]}
                else:
                    data = {"answer": "Returns are accepted within 14 days for unused items. Custom items are excluded. Please read the full policy.", "source_ids": [context["sources"][0]["id"]]}
            elif "classify a single user" in system:
                data = {"intent": "report"}
            elif "paid-social" in system:
                data = {"headlines": ["Thoughtful desk lighting"] * 3, "primary_texts": ["Explore our desk lamp collection."] * 3}
            else:
                data = {"headline": "Light your workspace", "subheadline": "Explore our desk lamps", "tagline": "Thoughtful lighting",
                        "cta": "Explore lamps", "header_cta": "Explore", "detail_bullets": ["Desk lamp"]}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(data)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 10}})

        ai_client._post = model
        product_hunter.search = lambda *a, **kw: SearchOutcome(results=[SearchResult("Desk lamp PKR 2000", "https://shop.example/lamp", "A desk lamp")], provider="test-transport")

        def transport(request):
            if "myshopify.com" in request.url.host:
                query = json.loads(request.content)
                if "SupportShop" in query["query"]:
                    return httpx.Response(200, json={"data": shop_data()})
                if "SupportCatalog" in query["query"]:
                    page = catalog([product(2)]) if query.get("variables", {}).get("after") else catalog([product()], "page-2")
                    return httpx.Response(200, json={"data": page})
                return httpx.Response(200, json={"data": {"shop": {"currencyCode": "PKR"}, "products": {"nodes": [{"id": "gid://shopify/Product/1", "title": "Imported lamp", "handle": "lamp", "description": "Desk lamp", "variants": {"nodes": [{"price": "2000"}]}}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}})
            if request.url.path.endswith("/insights"):
                return httpx.Response(200, json={"data": [{"account_name": "Test account", "account_currency": "PKR", "spend": "1000", "clicks": "100", "impressions": "5000", "date_start": "2026-10-01", "date_stop": "2026-10-23"}]})
            return httpx.Response(200, json={"id": "act_123456", "name": "Test account", "currency": "PKR", "account_status": 1})

        original_client = httpx.Client
        integrations.httpx.Client = lambda **kw: original_client(transport=httpx.MockTransport(transport), trust_env=False, **kw)
        uvicorn.run(app, host="127.0.0.1", port=8011, log_level="warning")


if __name__ == "__main__":
    main()
