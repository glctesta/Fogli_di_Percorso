"""Cattura screenshot delle pagine principali per la guida utente in romeno.

Usa Playwright per:
  1. Loggarsi (credenziali via argomenti command-line, non in chiaro nel codice).
  2. Cambiare lingua a RO via il selettore /lang/set/ro?next=...
  3. Per ogni pagina target, navigare + fare screenshot a tutta pagina.
  4. Salvare in docs/user-guide/capturi/<nome>.png

Uso:
  .venv/Scripts/python.exe scripts/capture_guide_screenshots.py --user gtesta --password "..."

Le credenziali NON sono salvate nello script o nel filesystem.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


# Pagine da catturare: (url_relativo, nome_file, descrizione)
PAGES = [
    ("/login", "01-login", "Pagina di autentificare"),
    ("/dashboard", "02-dashboard", "Pagina principala (dashboard)"),
    ("/coordinates", "03-punct-de-plecare", "Mappa per punctul de plecare"),
    ("/pathtracks", "04-lista-declaratii", "Lista declaratiilor mele"),
    ("/pathtracks/new", "05-noua-declaratie", "Formular declaratie noua"),
    ("/admin/representable", "06-admin-representable", "Colegii reprezentabili"),
    ("/admin/history", "07-admin-istoric", "Istoric SubCdc"),
    ("/admin/history?year=2026&month=5", "07b-admin-istoric-filtrat", "Istoric filtrat per anno+mese"),
    ("/admin/bnr-rates", "08-admin-bnr", "Cursuri BNR EUR-RON"),
    ("/admin/fuel-rates", "09-admin-fuel-rates", "Tarife rambursare km"),
]

BASE_URL = "http://127.0.0.1:5010"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "user-guide" / "capturi"

VIEWPORT = {"width": 1440, "height": 900}


def main(user: str, password: str, headed: bool = False) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {OUTPUT_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport=VIEWPORT, locale="ro-RO")
        page = context.new_page()

        # 1) Login page (catturare prima del login per il primo screenshot)
        print(f"\n[1] Capture login page (pre-login)")
        page.goto(f"{BASE_URL}/login")
        # Switch lingua a RO
        page.goto(f"{BASE_URL}/lang/set/ro?next=/login")
        page.wait_for_load_state("networkidle")
        out = OUTPUT_DIR / "01-login.png"
        page.screenshot(path=str(out), full_page=True)
        print(f"    saved {out.name}")

        # 2) Login
        print(f"\n[2] Login")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        page.fill('input[name="nome_user"]', user)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard", timeout=10000)
        print(f"    login OK, url={page.url}")

        # 3) Per ogni pagina (escludendo login che è già fatta), naviga e screenshot
        for url_path, fname, desc in PAGES[1:]:
            print(f"\n[+] Capture: {desc}  ({url_path})")
            try:
                page.goto(f"{BASE_URL}{url_path}", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=5000)
                # piccola attesa per render finale (mappe leaflet, etc)
                page.wait_for_timeout(800)
                out = OUTPUT_DIR / f"{fname}.png"
                page.screenshot(path=str(out), full_page=True)
                print(f"    saved {out.name}")
            except Exception as e:
                print(f"    FAILED: {e}")

        browser.close()

    print(f"\nDone. {len(PAGES)} screenshots in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--headed", action="store_true", help="Mostra finestra browser (default headless)")
    args = ap.parse_args()
    sys.exit(main(args.user, args.password, args.headed))
