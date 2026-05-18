"""Aggiorna interattivamente config/workplace.json con coordinate reali.

Eseguire dalla cartella principale del progetto:

    .venv\\Scripts\\python.exe scripts\\set_workplace.py

Lo script chiede nome, indirizzo, latitudine e longitudine del luogo
di lavoro e scrive il file in modo formattato.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKPLACE_JSON = ROOT / "config" / "workplace.json"


def _ask_float(prompt: str) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            return float(raw)
        except ValueError:
            print(f"  '{raw}' non e' un numero valido. Riprovare.")


def main() -> int:
    print("=" * 60)
    print("Fogli di Percorso - Configurazione luogo di lavoro")
    print("=" * 60)
    print()
    print(f"Aggiornera': {WORKPLACE_JSON}")
    print()

    name = input("Nome sede [Sede aziendale]: ").strip() or "Sede aziendale"
    address = input("Indirizzo completo: ").strip()
    if not address:
        print("ERRORE: indirizzo obbligatorio.", file=sys.stderr)
        return 1

    print()
    print("Coordinate (puoi prenderle da Google Maps: click destro -> click sulle coordinate)")
    lat = _ask_float("Latitudine (es. 50.5234): ")
    lon = _ask_float("Longitudine (es. 3.2891): ")

    if not (-90 <= lat <= 90):
        print(f"ERRORE: latitudine {lat} fuori range [-90, 90].", file=sys.stderr)
        return 1
    if not (-180 <= lon <= 180):
        print(f"ERRORE: longitudine {lon} fuori range [-180, 180].", file=sys.stderr)
        return 1

    data = {"name": name, "address": address, "lat": lat, "lon": lon}

    WORKPLACE_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"OK -> {WORKPLACE_JSON} aggiornato:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
