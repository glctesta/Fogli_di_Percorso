"""One-shot script to fill missing EN/RO translations after pybabel update.

Reads each .po file, finds msgid blocks with empty msgstr, looks up the
translation in TRANSLATIONS dict, and writes it back. Idempotent: re-running
on an already-filled file is a no-op.

Usage:
    .venv/Scripts/python.exe scripts/fill_translations.py
"""
from __future__ import annotations

import re
from pathlib import Path


# Translations for the newly extracted strings. Add more as templates change.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # admin/routes.py flash messages (fuel-rates POST)
        "Consumo (km/L) non valido.": "Invalid consumption (km/L).",
        "Consumo (km/L) deve essere positivo.": "Consumption (km/L) must be positive.",
        "Prezzo carburante (EUR/L) non valido.": "Invalid fuel price (EUR/L).",
        "Prezzo carburante (EUR/L) deve essere positivo.": "Fuel price (EUR/L) must be positive.",
        "'Valido fino a' non puo' essere precedente a 'valido da'.": "'Valid to' cannot be before 'valid from'.",
        "Esiste gia' una tariffa con questo 'valido da'.": "A tariff with this 'valid from' already exists.",
        "Tariffa inserita (consumo=%(c).2f km/L, prezzo=%(p).3f EUR/L).": "Tariff inserted (consumption=%(c).2f km/L, price=%(p).3f EUR/L).",
        # Lang selector label
        "Lingua": "Language",
        # representable.html link
        "Gestisci tariffe €/km": "Manage €/km tariffs",
        # fuel_rates.html template
        "Tariffe rimborso km": "Km reimbursement tariffs",
        "Gestione tariffe rimborso km": "Km reimbursement tariffs management",
        "Inserisci nuova tariffa": "Insert new tariff",
        "Consumo medio (km/L)": "Average consumption (km/L)",
        "Prezzo medio carburante (EUR/L)": "Average fuel price (EUR/L)",
        "Salva tariffa": "Save tariff",
        "Tariffe attive e storiche": "Active and historical tariffs",
        "Consumo km/L": "Consumption km/L",
        "Prezzo EUR/L": "Price EUR/L",
        "€/km": "€/km",
        "(aperto)": "(open)",
        "Nessuna tariffa configurata.": "No tariff configured.",
        # one EN-only stale: still missing
        "L'invio sara' possibile solo dal 1 al 5 del mese successivo.":
            "Submission is only available between the 1st and 5th of the following month.",
        # representable.html intro paragraph (was hardcoded)
        "Puoi inserire dichiarazioni e gestire punti di partenza per conto dei colleghi elencati qui sotto (stesso SubCdc, FunctionCode minore della tua).":
            "You can submit declarations and manage starting points on behalf of the colleagues listed below (same SubCdc, lower FunctionCode than yours).",
    },
    "ro": {
        # admin/routes.py flash messages (fuel-rates POST)
        "Consumo (km/L) non valido.": "Consum (km/L) invalid.",
        "Consumo (km/L) deve essere positivo.": "Consumul (km/L) trebuie sa fie pozitiv.",
        "Prezzo carburante (EUR/L) non valido.": "Pret combustibil (EUR/L) invalid.",
        "Prezzo carburante (EUR/L) deve essere positivo.": "Pretul combustibilului (EUR/L) trebuie sa fie pozitiv.",
        "'Valido fino a' non puo' essere precedente a 'valido da'.": "'Valabil pana la' nu poate fi inainte de 'valabil de la'.",
        "Esiste gia' una tariffa con questo 'valido da'.": "Exista deja o tarifare cu acest 'valabil de la'.",
        "Tariffa inserita (consumo=%(c).2f km/L, prezzo=%(p).3f EUR/L).": "Tarif inserat (consum=%(c).2f km/L, pret=%(p).3f EUR/L).",
        # Lang selector label
        "Lingua": "Limba",
        # representable.html link
        "Gestisci tariffe €/km": "Gestioneaza tarifele €/km",
        # fuel_rates.html template
        "Tariffe rimborso km": "Tarife rambursare km",
        "Gestione tariffe rimborso km": "Gestionare tarife rambursare km",
        "Inserisci nuova tariffa": "Adauga tarifa noua",
        "Consumo medio (km/L)": "Consum mediu (km/L)",
        "Prezzo medio carburante (EUR/L)": "Pret mediu combustibil (EUR/L)",
        "Salva tariffa": "Salveaza tariful",
        "Tariffe attive e storiche": "Tarife active si istorice",
        "Consumo km/L": "Consum km/L",
        "Prezzo EUR/L": "Pret EUR/L",
        "€/km": "€/km",
        "(aperto)": "(deschis)",
        "Nessuna tariffa configurata.": "Nicio tarifa configurata.",
        # one RO-only stale: still missing
        "Confermi l'invio definitivo? Dopo l'invio non potrai più modificare.":
            "Confirmi trimiterea definitiva? Dupa trimitere nu vei mai putea modifica.",
        # representable.html intro paragraph (was hardcoded)
        "Puoi inserire dichiarazioni e gestire punti di partenza per conto dei colleghi elencati qui sotto (stesso SubCdc, FunctionCode minore della tua).":
            "Poti introduce declaratii si gestiona puncte de plecare in numele colegilor listati mai jos (acelasi SubCdc, FunctionCode mai mic decat al tau).",
    },
}


# Match a single-line msgid followed by an empty msgstr "".
# Captures the msgid value so we can look it up in TRANSLATIONS.
PAIR_RE = re.compile(
    r'^(msgid "((?:[^"\\]|\\.)+)"\n)msgstr ""\n',
    re.MULTILINE,
)


def fill_file(po_path: Path, translations: dict[str, str]) -> int:
    """Fill empty msgstr entries in po_path using translations. Returns count filled."""
    text = po_path.read_text(encoding="utf-8")
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        msgid_block = m.group(1)
        msgid_value = m.group(2)
        # Unescape \" → "
        msgid_unescaped = msgid_value.replace('\\"', '"')
        if msgid_unescaped in translations:
            translation = translations[msgid_unescaped]
            # Escape " for msgstr value
            translation_escaped = translation.replace('"', '\\"')
            count += 1
            return f'{msgid_block}msgstr "{translation_escaped}"\n'
        return m.group(0)

    new_text = PAIR_RE.sub(repl, text)
    if count > 0:
        po_path.write_text(new_text, encoding="utf-8")
    return count


def main() -> None:
    base = Path("fdp_app/translations")
    for lang, translations in TRANSLATIONS.items():
        po_path = base / lang / "LC_MESSAGES" / "messages.po"
        if not po_path.exists():
            print(f"SKIP {po_path}: not found")
            continue
        count = fill_file(po_path, translations)
        print(f"{lang}: filled {count} entries in {po_path}")


if __name__ == "__main__":
    main()
