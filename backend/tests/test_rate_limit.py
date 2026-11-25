import pytest

import app as app_module
from services import rate_limit
from services.rate_limit import retry_after


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_allows_up_to_the_limit_then_says_how_long_to_wait():
    rules = [(3, 60)]
    assert [retry_after("k", rules, now=t) for t in (0, 1, 2)] == [None, None, None]
    assert retry_after("k", rules, now=10) == 50


def test_window_slides():
    rules = [(2, 60)]
    retry_after("k", rules, now=0)
    retry_after("k", rules, now=30)
    assert retry_after("k", rules, now=59) == 1
    assert retry_after("k", rules, now=60) is None


def test_every_rule_applies():
    rules = [(5, 60), (6, 3600)]
    for t in range(5):
        assert retry_after("k", rules, now=t) is None
    assert retry_after("k", rules, now=61) is None
    assert retry_after("k", rules, now=200) == 3600 - 200


def test_blocked_requests_do_not_count():
    rules = [(1, 60)]
    retry_after("k", rules, now=0)
    for t in range(1, 50):
        retry_after("k", rules, now=t)
    assert retry_after("k", rules, now=60) is None


def test_keys_are_separate():
    rules = [(1, 60)]
    assert retry_after("a", rules, now=0) is None
    assert retry_after("b", rules, now=0) is None


def test_old_keys_are_dropped_when_many_build_up(monkeypatch):
    for i in range(5001):
        rate_limit._hits[("old", i)] = rate_limit.deque([0.0])
    retry_after("new", [(1, 60)], now=2 * 24 * 60 * 60)
    assert list(rate_limit._hits) == ["new"]


def test_route_returns_429_with_retry_after(client):
    for _ in range(20):
        client.post("/locate", json={})
    response = client.post("/locate", json={})
    assert response.status_code == 429
    assert response.get_json()["error"] == app_module.TOO_MANY
    assert int(response.headers["Retry-After"]) >= 1


def test_each_visitor_gets_their_own_limit(client):
    for _ in range(20):
        client.post("/locate", json={}, headers={"CF-Connecting-IP": "203.0.113.1"})
    assert client.post("/locate", json={}, headers={"CF-Connecting-IP": "203.0.113.1"}).status_code == 429
    assert client.post("/locate", json={}, headers={"CF-Connecting-IP": "203.0.113.2"}).status_code == 400


def test_preflight_requests_are_not_counted(client):
    for _ in range(30):
        client.options("/locate")
    assert client.post("/locate", json={}).status_code == 400


def test_every_route_has_a_limit():
    routes = {r.rule for r in app_module.app.url_map.iter_rules() if r.endpoint != "static"}
    assert routes == set(app_module.RATE_LIMITS)
