# Admin — gestione tariffe rimborso km

**Data:** 2026-05-25
**Stato:** spec
**Autore:** brainstorming session

## 1. Obiettivo

Permettere agli utenti admin di inserire nuove versioni dei parametri usati per il calcolo del rimborso carburante (consumo medio e prezzo medio carburante), oggi modificabili solo via SQL. Resta valido il pattern già adottato per i tassi BNR EUR-RON: insert-only, versionato per `ValidFrom`, accessibile dall'area `/admin/representable`.

## 2. Contesto

La tabella `Employee.fdp.PathTrackReimbursementRates` esiste già (creata in `sql/001_init.sql`) ed è letta da `fdp_app/repos/rate_repo.py::RateRepo.find_for_date`. La formula di rimborso in `fdp_app/pathtracks/calculator.py::compute_fuel_reimbursement` è:

```
litri = (km_andata * 2 * viaggi) / consumo_km_l
eur   = litri * prezzo_eur_l
```

Quindi l'€/km effettivo è `prezzo_eur_l / consumo_km_l`. Lo storico dei rimborsi già emessi referenzia il `RateId` congelato in `PathTracks.RateIdUsed`, quindi nuovi inserimenti **non** alterano retroattivamente nessun calcolo.

## 3. Decisioni

- **Modello dati invariato.** Si continuano a salvare due valori (`AvgConsumptionKmL`, `AvgFuelPriceEurL`). Nessuna migration. L'€/km è solo una colonna *calcolata e visualizzata* in pagina.
- **Insert-only.** Ogni cambio è una nuova riga con `ValidFrom`/`ValidTo`. Nessuna edit, nessun delete. Lo storico è immutabile (audit-safe).
- **Permessi.** Stesso `@login_required` + `@admin_required` usato dagli altri endpoint admin; nessun nuovo decorator né soglia FunctionCode dedicata.
- **Navigazione.** Link da `/admin/representable` accanto a "Gestisci tassi BNR EUR-RON".

## 4. Architettura

Nuovo endpoint coppia GET/POST: `/admin/fuel-rates`.

| Componente | File | Modifica |
| --- | --- | --- |
| Repository | `fdp_app/repos/rate_repo.py` | Estensione: nuovi metodi `insert`, `list_recent`; dataclass `Rate` arricchito di campi audit opzionali |
| Route | `fdp_app/admin/routes.py` | Aggiunta endpoint `fuel_rates` (GET) e `fuel_rates_create` (POST) |
| Template | `fdp_app/templates/admin/fuel_rates.html` | Nuovo file |
| Navigazione | `fdp_app/templates/admin/representable.html` | Aggiunto link al nuovo endpoint |
| Test | `tests/test_admin_fuel_rates.py` | Nuovo file |

## 5. Repository — `rate_repo.py`

Il modulo esistente viene esteso, non sostituito. Il dataclass `Rate` acquisisce tre campi opzionali (default `None`/`""`) in modo che `find_for_date` continui a funzionare senza modifiche:

```python
@dataclass(frozen=True)
class Rate:
    rate_id: int
    avg_consumption_km_l: float
    avg_fuel_price_eur_l: float
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    user_sys: str = ""
```

Nuovi metodi:

```python
def insert(self, *, avg_consumption_km_l: float, avg_fuel_price_eur_l: float,
           valid_from: date, valid_to: Optional[date],
           user_sys: str) -> int:
    """INSERT ... OUTPUT INSERTED.RateId. May raise pyodbc.IntegrityError
    se viene violato UX_Rates_ValidFrom (ValidFrom duplicato)."""

def list_recent(self, *, limit: int = 20) -> List[Rate]:
    """SELECT TOP (?) ... ORDER BY ValidFrom DESC, RateId DESC."""
```

Le query SQL sono moduli-level constants come in `bnr_rate_repo.py`.

## 6. Route — `admin/routes.py`

```python
@bp.route("/fuel-rates", methods=["GET"])
@login_required
@admin_required
def fuel_rates():
    repo = RateRepo(current_app.config["_db"])
    recent = repo.list_recent(limit=20)
    return render_template("admin/fuel_rates.html", recent=recent)

@bp.route("/fuel-rates", methods=["POST"])
@login_required
@admin_required
def fuel_rates_create():
    # parse + validate, repo.insert, flash, redirect
```

Validazione (ogni errore → `flash` + `redirect(url_for("admin.fuel_rates"))`, l'insert non avviene):

| Campo | Regola |
| --- | --- |
| `avg_consumption_km_l` | parse `float`, deve essere `> 0` |
| `avg_fuel_price_eur_l` | parse `float`, deve essere `> 0` |
| `valid_from` | `date.fromisoformat`, obbligatorio |
| `valid_to` | opzionale; se presente deve essere `>= valid_from` |
| `ValidFrom` duplicato | `pyodbc.IntegrityError` catturato → flash "Esiste già un tasso con questo 'Valido da'" |

`user_sys = session.get("full_name") or "admin"`. Log info con `current_app.logger.info(...)` su successo (stesso formato del corrispettivo BNR).

## 7. Template — `templates/admin/fuel_rates.html`

Calca `bnr_rates.html`:

- `<h2>` con `bi-fuel-pump` + titolo "Tariffe rimborso km".
- Paragrafo `text-muted` che spiega: ogni inserimento crea una nuova versione, lo storico dei rimborsi già registrati resta congelato.
- Form `POST /admin/fuel-rates` con `csrf_token` hidden:
  - `avg_consumption_km_l` — `type="number"`, `step="0.01"`, `min="0.01"`, placeholder `15.00`, label "Consumo medio (km/L)"
  - `avg_fuel_price_eur_l` — `type="number"`, `step="0.001"`, `min="0.001"`, placeholder `1.700`, label "Prezzo medio carburante (EUR/L)"
  - `valid_from` — `type="date"`, `required`
  - `valid_to` — `type="date"`, opzionale
  - bottone submit "Salva tariffa"
- Tabella "Ultime tariffe" con colonne: **Consumo km/L · Prezzo EUR/L · €/km · Valido da · Valido fino a · Inserito da**. La colonna €/km è `prezzo / consumo` formattata a 4 decimali; valida-fino-a vuota mostra "(aperto)".
- Stato vuoto: alert info "Nessuna tariffa configurata."
- Link `<a class="btn btn-link">` finale verso `admin.representable`.

Tutte le stringhe attraverso `_()` per i18n, in linea con il resto del modulo.

## 8. Navigazione — `templates/admin/representable.html`

In fondo alla pagina, accanto a "Gestisci tassi BNR EUR-RON", aggiunto:

```jinja
<a href="{{ url_for('admin.fuel_rates') }}" class="btn btn-link mt-3">
    <i class="bi bi-fuel-pump"></i> {{ _('Gestisci tariffe €/km') }}
</a>
```

## 9. Test — `tests/test_admin_fuel_rates.py`

Nuovo file, struttura analoga a `test_admin_bnr_rates.py`. Casi:

1. `test_fuel_rates_requires_admin` — utente non-admin → 403.
2. `test_fuel_rates_empty_state` — tabella vuota, alert info mostrato.
3. `test_fuel_rates_lists_rates` — un record di esempio appare con consumo, prezzo, €/km calcolato, valid_from.
4. `test_fuel_rates_create` — POST valido completo chiama `repo.insert` con i kwargs corretti, redirect 302.
5. `test_fuel_rates_create_without_valid_to` — kwargs.valid_to is None.
6. `test_fuel_rates_create_rejects_invalid_consumption` — consumo non parsabile → no insert.
7. `test_fuel_rates_create_rejects_non_positive_consumption` — consumo `<= 0` → no insert.
8. `test_fuel_rates_create_rejects_non_positive_price` — prezzo `<= 0` → no insert.
9. `test_fuel_rates_create_rejects_invalid_valid_from` — data non parsabile → no insert.
10. `test_fuel_rates_create_rejects_valid_to_before_valid_from` → no insert.
11. `test_fuel_rates_create_handles_duplicate_valid_from` — `repo.insert.side_effect = pyodbc.IntegrityError(...)`; il route non crasha, redirect con flash.

Mock di `RateRepo` via `patch("fdp_app.admin.routes.RateRepo")`.

## 10. YAGNI (cosa NON facciamo)

- Niente edit né delete di record esistenti: lo storico resta immutabile.
- Niente chiusura automatica della versione "aperta" precedente quando se ne inserisce una nuova: la gestione di `ValidTo` resta esplicita, come per BNR.
- Niente nuovo ruolo o decorator: si usa `@admin_required`.
- Niente modifiche a `calculator.py`, a `RateRepo.find_for_date`, alle pagine pathtracks o agli script SQL.
- Niente export XLSX della lista tariffe (BNR non ce l'ha; il volume è basso).

## 11. Rischi e mitigazioni

| Rischio | Mitigazione |
| --- | --- |
| Admin inserisce un duplicato di `ValidFrom` | Catch `pyodbc.IntegrityError` → flash chiaro. Nessun 500. |
| Admin inserisce valori plausibili ma sbagliati di un ordine di grandezza (es. 1.7 km/L invece di 15) | Validazione `> 0` è sufficiente per il dominio; valori "strani" sono rilevabili in tabella prima del prossimo submit. YAGNI su bound espliciti. |
| `Rate` dataclass esteso rompe consumatori esistenti | I tre nuovi campi hanno default → costruzioni esistenti continuano a funzionare. Verificato in `find_for_date` (l'unica chiamata di costruzione attiva). |
