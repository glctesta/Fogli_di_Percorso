"""Helpers admin: generazione XLSX in memoria."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


def build_xlsx(rows, *, year: int, month: int, month_name: str) -> bytes:
    """Genera un XLSX con una riga per PathTrackWithEmployee.

    rows: iterable di PathTrackWithEmployee
    """
    wb = Workbook()
    ws = wb.active
    ws.title = f"{month_name} {year}"

    headers = [
        "Cognome", "Nome", "Tipo", "Stato", "N. Viaggi A/R", "Km one-way",
        "Importo EUR", "N. Registro", "Data invio",
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="0B2A5B")
    header_align = Alignment(horizontal="center")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    for entry in rows:
        ws.append([
            entry.employee_surname,
            entry.employee_name,
            entry.row.reimbursement_type,
            entry.row.status,
            entry.row.number_of_trips,
            entry.row.road_km,
            entry.row.computed_amount_eur,
            entry.row.registry_id or "",
            entry.row.submitted_on.strftime("%d/%m/%Y %H:%M") if entry.row.submitted_on else "",
        ])

    # Auto-width approssimativo
    for col in ws.columns:
        length = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(length + 2, 50)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
