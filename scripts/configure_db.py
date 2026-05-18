"""Configura interattivamente le credenziali DB cifrate.

Eseguire UNA TANTUM dalla cartella principale del progetto:

    .venv\\Scripts\\python.exe scripts\\configure_db.py

Lo script chiede server, database, username e password (quest'ultima
non viene mostrata a video) e li cifra in `db_config.enc` tramite
`ConfigManager` esistente. La chiave di cifratura e' in `encryption_key.key`.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Assicura che la project root sia sull'import path quando lo script
# viene lanciato da una sottocartella.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config_manager import ConfigManager  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("Fogli di Percorso - Configurazione credenziali DB")
    print("=" * 60)
    print()
    print("I valori inseriti saranno cifrati in db_config.enc")
    print("(file gia' presente nel .gitignore, NON finisce su GitHub).")
    print()

    server = input("SQL Server (es. host\\istanza o host,1433): ").strip()
    if not server:
        print("ERRORE: server obbligatorio.", file=sys.stderr)
        return 1

    database = input("Database [default: Employee]: ").strip() or "Employee"

    username = input("Username SQL Server: ").strip()
    if not username:
        print("ERRORE: username obbligatorio.", file=sys.stderr)
        return 1

    password = getpass.getpass("Password (non verra' mostrata): ")
    if not password:
        print("ERRORE: password obbligatoria.", file=sys.stderr)
        return 1

    # Il driver passato qui e' indicativo: db_connection.py sceglie
    # automaticamente il primo driver ODBC disponibile sulla macchina.
    driver = "ODBC Driver 18 for SQL Server"

    cm = ConfigManager()
    cm.save_config(
        driver=driver,
        server=server,
        database=database,
        username=username,
        password=password,
    )

    print()
    print(f"OK -> db_config.enc aggiornato.")
    print(f"     Server   = {server}")
    print(f"     Database = {database}")
    print(f"     Username = {username}")
    print(f"     Password = (cifrata, non mostrata)")
    print()
    print("Prossimo passo: avviare l'app con 'flask --app app run'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
