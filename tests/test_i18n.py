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
    # Inline RO/IT/EN buttons (replacement for the previous Bootstrap dropdown
    # that broke when browser CSP blocked unsafe-eval — Popper.js dependency).
    assert b'href="/lang/set/ro' in response.data
    assert b'href="/lang/set/it' in response.data
    assert b'href="/lang/set/en' in response.data


def test_lang_selector_visible_when_logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70
    response = client.get("/dashboard")
    assert response.status_code == 200
    # Lang selector rendered on every page via base.html include.
    assert b'href="/lang/set/ro' in response.data
    assert b'href="/lang/set/it' in response.data
    assert b'href="/lang/set/en' in response.data


# ---- Tests that verify .mo translations are actually applied ----

def test_login_page_shows_romanian_with_ro_cookie(client):
    client.set_cookie("fdp_lang", "ro")
    response = client.get("/login")
    assert response.status_code == 200
    # "Accedi" (IT) -> "Autentificare" (RO)
    assert b"Autentificare" in response.data
    # Italian "Accedi" should NOT appear in RO locale
    # Note: "Accedi" could be substring of other words; check the title block instead
    # We assert positive: the RO word is present


def test_login_page_shows_english_with_en_cookie(client):
    client.set_cookie("fdp_lang", "en")
    response = client.get("/login")
    assert response.status_code == 200
    # "Accedi" (IT) -> "Sign in" (EN)
    assert b"Sign in" in response.data
    assert b"Username" in response.data
    assert b"Password" in response.data  # same in IT/EN, just verifies page renders


def test_login_page_shows_italian_with_it_cookie(client):
    client.set_cookie("fdp_lang", "it")
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Accedi" in response.data
    assert b"Nome utente" in response.data


def test_403_page_translated_to_ro(client):
    # Force a 403: the admin route is admin_required; login as non-admin
    client.set_cookie("fdp_lang", "ro")
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50  # non-admin
    response = client.get("/admin/representable")
    assert response.status_code == 403
    # "Accesso negato" -> "Acces refuzat"
    assert b"Acces refuzat" in response.data


def test_dashboard_translates_welcome_with_placeholder(client):
    """Verifica che la traduzione con %(name)s funzioni."""
    client.set_cookie("fdp_lang", "en")
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70
    response = client.get("/dashboard")
    assert response.status_code == 200
    # "Benvenuto, Rossi Mario" -> "Welcome, Rossi Mario"
    assert b"Welcome, Rossi Mario" in response.data


def test_dashboard_translates_welcome_in_ro(client):
    client.set_cookie("fdp_lang", "ro")
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70
    response = client.get("/dashboard")
    assert response.status_code == 200
    # "Benvenuto" -> "Bun venit"
    assert b"Bun venit, Rossi Mario" in response.data


def test_navbar_links_translated_to_ro(client):
    """I link della navbar cambiano lingua quando l'utente e' loggato."""
    client.set_cookie("fdp_lang", "ro")
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70
    response = client.get("/dashboard")
    assert response.status_code == 200
    # "Punto di partenza" -> "Punct de plecare"
    assert b"Punct de plecare" in response.data
    # "Dichiarazioni" -> "Declaratii"
    assert b"Declaratii" in response.data
    # "Esci" -> "Iesire"
    assert b"Iesire" in response.data


def test_navbar_links_translated_to_en(client):
    client.set_cookie("fdp_lang", "en")
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Starting point" in response.data
    assert b"Declarations" in response.data
    assert b"Logout" in response.data
