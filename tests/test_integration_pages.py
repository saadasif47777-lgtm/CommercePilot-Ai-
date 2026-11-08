"""Pagination and candidate verification use provider-shaped responses."""
import httpx
import pytest

from commercepilot import config, integrations


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setattr(integrations, '_saved', lambda provider: {})
    monkeypatch.setattr(integrations, 'mark_verified', lambda *args: None)
    monkeypatch.setattr(config, 'SHOPIFY_SHOP_DOMAIN', 'store.myshopify.com')
    monkeypatch.setattr(config, 'SHOPIFY_ADMIN_TOKEN', 'test-token')
    monkeypatch.setattr(config, 'META_ACCESS_TOKEN', 'test-token')
    monkeypatch.setattr(config, 'META_AD_ACCOUNT_ID', 'act_123')
    original = httpx.Client
    def configure(handler):
        monkeypatch.setattr(integrations.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handler), trust_env=False, **kw))
    return configure


def test_shopify_page_cursor_and_scope_validation(transport):
    import json
    calls = []
    def handler(request):
        data = json.loads(request.content)
        calls.append(data['variables'])
        return httpx.Response(200, json={"data": {
            "shop": {"currencyCode": "USD", "myshopifyDomain": "store.myshopify.com"},
            "currentAppInstallation": {"accessScopes": [{"handle": "read_products"}]},
            "products": {
                "nodes": [{"id": "p2", "title": "Second page", "variants": {"nodes": [{"price": "0"}]}}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }})
    transport(handler)
    result = integrations.shopify_fetch_products(50, after='page-2')
    assert result['products'][0]['page_after'] == 'page-2'
    assert result['products'][0]['price'] == '0'
    assert calls[0]['after'] == 'page-2'
    assert integrations.shopify_fetch_products(candidate={'shop_domain': 'other.myshopify.com', 'admin_token': 'candidate'})['ok'] is False


def test_meta_pagination_never_follows_provider_supplied_url(transport):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'data': [], 'paging': {'next': 'https://untrusted.example/token', 'cursors': {'after': 'page2'}}})
    transport(handler)
    result = integrations.meta_insights()
    assert result['next_cursor'] == 'page2'
    integrations.meta_insights(after=result['next_cursor'])
    assert all(r.url.host == 'graph.facebook.com' for r in calls)
    assert calls[-1].url.params['after'] == 'page2'
