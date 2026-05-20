"""Test i18n: locale selector, cookie management."""
from __future__ import annotations

import pytest


def test_language_selector_endpoint_sets_cookie(client):
    response = client.post("/lang/en", data={"next": "/"}, follow_redirects=False)
    assert response.status_code == 302
    cookies = response.headers.getlist("Set-Cookie")
    assert any("fdp_lang=en" in c for c in cookies)


def test_language_selector_redirects_to_next(client):
    response = client.post("/lang/it", data={"next": "/dashboard"},
                            follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_language_selector_rejects_invalid_code(client):
    response = client.post("/lang/xx", follow_redirects=False)
    assert response.status_code == 400


def test_default_locale_is_ro_when_no_cookie_no_header(client):
    # Hit a page that doesn't require login: /login
    response = client.get("/login")
    assert response.status_code == 200
    # The lang selector should show RO flag (default)
    assert b"RO" in response.data


def test_lang_selector_partial_rendered_on_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    # Should contain the language dropdown
    assert b"dropdown-toggle" in response.data
    # All three flags present in the dropdown items
    # (we test text since the emoji bytes are tricky)
    assert b"Romana" in response.data
    assert b"English" in response.data
    assert b"Italiano" in response.data


def test_lang_selector_visible_when_logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"dropdown-toggle" in response.data
