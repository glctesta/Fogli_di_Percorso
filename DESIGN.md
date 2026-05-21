# Design System — Fogli di Percorso

> Sistema visivo dell'app. Implementato in `fdp_app/static/css/app.css` con
> Bootstrap 5.3.3 come framework di base. Bootstrap Icons 1.11.3 per le icone.

## Colors

### Brand
| Token | Hex | Uso |
|---|---|---|
| `--fdp-primary` | `#0b2a5b` | Navbar, h2-h5, button primary, table header, badge SUBMITTED |
| `--fdp-primary-dark` | `#07193b` | Hover/active del primary |
| `--fdp-accent` | `#1d9bf0` | Link, focus ring, icone dashboard cards, importo evidenziato, bordo inferiore navbar |
| `--fdp-bg` | `#f5f7fb` | Body background (off-white) |
| `--fdp-surface` | `#ffffff` | Card, tabelle, footer |
| `--fdp-border` | `#e3e7ef` | Bordi soft, separator hr |
| `--fdp-muted` | `#6b7280` | Testo secondario, form-text helper |

### Stati
- Successo (DRAFT salvata, SUBMIT OK): `#d1fae5` bg + `#065f46` testo
- Warning (BOZZA badge, BNR rate stale): `#fef3c7` bg + `#92400e` testo
- Danger (errori validazione, cancellazione): `#fee2e2` bg + `#991b1b` testo
- Info (note informative): `#dbeafe` bg + `#1e40af` testo

## Typography

### Stack
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
             Roboto, "Helvetica Neue", Arial, sans-serif;
```

### Scale
| Element | Size | Weight | Color |
|---|---|---|---|
| `h1` (raro) | 2rem | 600 | `--fdp-primary` |
| `h2` (page title) | 1.75rem | 600 | `--fdp-primary` + border-bottom 2px |
| `h3` (section) | 1.5rem | 600 | `--fdp-primary` |
| `h4` (sub-section) | 1.25rem | 600 | `--fdp-primary` |
| `h5` (card-title) | 1.125rem | 600 | `--fdp-primary` |
| `body` | 1rem | 400 | `#1f2937` |
| `.form-label` | 0.875rem | 500 | `#374151` |
| `.form-text` | 0.875rem | 400 | `--fdp-muted` |
| `.amount-preview` | 1.75rem | 700 | `--fdp-primary` + bg ciano translucido |

## Spacing

- Base: Bootstrap default (rem-based: `g-3` = 1rem gap, `mb-4` = 1.5rem)
- Container max-width: Bootstrap default
- Card padding: `1rem` di default, `1.75rem` per le `fdp-dashboard-card`
- Form gap: `mb-3` (1rem) tra campi
- Section gap: `mt-4` / `mb-4` tra blocchi logici

## Components

### Navbar (`.fdp-navbar`)
- Background: linear-gradient navy (135deg da `--fdp-primary` a `--fdp-primary-dark`)
- Border-bottom: 3px solid `--fdp-accent`
- Shadow: `shadow-sm` (subtle elevation)
- Brand: logo (height 36px, padding 3px 5px, bg bianco, rounded 6px) + nome
- Nav-links: peso 500, hover bianco pieno
- Lang selector: dropdown con bandiere emoji
- Margin-bottom: `mb-4` (1.5rem)

### Cards (`.card`)
- Border: 1px solid `--fdp-border`
- Border-radius: 10px
- Shadow base: `0 1px 3px rgba(11, 42, 91, 0.04)` (quasi invisibile)
- Shadow hover: `0 4px 12px rgba(11, 42, 91, 0.08)` (lift)
- Transition: 0.2s ease-in-out
- Card-title: navy + peso 600

### Dashboard cards (`.fdp-dashboard-card`)
- Padding body: 1.75rem
- Icona Bootstrap Icons grande: 2.5rem, color `--fdp-accent`, display block, margin-bottom 0.75rem
- CTA button: btn-outline-primary con freccia destra `bi-arrow-right`

### Tables (`.table`)
- Background: `--fdp-surface`
- Border-radius: 8px (con `overflow: hidden`)
- Thead: bg `--fdp-primary`, testo bianco, peso 500, padding 0.85rem
- Stripe rows: tinta blu sottilissima `rgba(11, 42, 91, 0.02)` su righe dispari
- Compact variant: `table-sm` per recent BNR rates

### Buttons
- `btn-primary`: bg navy, hover dark navy, peso 500
- `btn-outline-primary`: border navy + testo navy, hover bg navy + testo bianco
- `btn-warning`: bg giallo Bootstrap (per admin override / BOZZA)
- `btn-outline-danger`: per delete actions
- Icone Bootstrap a sinistra del testo (`<i class="bi bi-xxx"></i> Label`)
- Size: default `btn` per primary actions, `btn-sm` in tabelle, `btn-lg` solo per login CTA

### Forms
- Input `form-control` + `form-control-lg` su login (visibilità)
- Focus: border `--fdp-accent`, box-shadow `0 0 0 0.2rem rgba(29, 155, 240, 0.18)`
- Radio/checkbox checked: bg `--fdp-primary`
- Validation: Bootstrap default (rosso danger)
- Required: nessun asterisco (gli input HTML lo fanno via `required`)

### Alerts
- Border: none (background-only, più moderno)
- Border-radius: 8px
- Dismissible: con icona `×` a destra (Bootstrap JS)
- Shadow: `shadow-sm`
- Tipi: success/danger/warning/info (vedi Colors > Stati)

### Map container (`.map-container`)
- Height: 500px (480 su mobile)
- Border: 1px solid `--fdp-border`
- Border-radius: 10px
- Shadow interno: `inset 0 0 0 1px rgba(0, 0, 0, 0.02)`
- Overflow: hidden (per arrotondare i tile)

### Badges (stato)
- `bg-warning text-dark` = "BOZZA" / "CIORNA" / "DRAFT"
- `bg-success` = "INVIATA" / "TRIMISA" / "SUBMITTED"

### Login card (`.fdp-login-card`)
- Max-width: 420px
- Centered: `.fdp-login-wrapper` con `display: flex; align-items: center; justify-content: center; min-height: calc(100vh - 240px)`
- Border-radius: 14px
- Shadow: `0 10px 40px rgba(11, 42, 91, 0.12)` (più pronunciata, è la pagina di ingresso)
- Logo dentro: height 64px, margin-bottom 1rem
- Form text-align-start (no center per i campi)

### Footer (`.fdp-footer`)
- Background: `--fdp-surface`
- Border-top: 1px solid `--fdp-border`
- Padding: 1rem 0
- Text-align: center
- Logo footer: 22px height, vertical-middle
- Position: sticky bottom via `body.d-flex flex-column min-vh-100` + `mt-auto`

## Iconography

Bootstrap Icons 1.11.3, sempre prefissate. Mapping uso:

| Icona | Contesto |
|---|---|
| `bi-house-door` | Home/Dashboard |
| `bi-geo-alt` | Coordinate, punto di partenza |
| `bi-receipt` | Dichiarazione, lista |
| `bi-people-fill` | Admin / rappresentanza |
| `bi-clock-history` | Storico |
| `bi-file-earmark-excel` | Export XLSX |
| `bi-file-earmark-pdf` | Download PDF |
| `bi-download` | Download generico |
| `bi-currency-exchange` | Tassi BNR |
| `bi-person-circle` | Utente loggato (navbar) |
| `bi-box-arrow-right` | Logout |
| `bi-box-arrow-in-right` | Login button |
| `bi-save` | Salva bozza |
| `bi-send-check` | Conferma e invia |
| `bi-shield-check` | Admin override |
| `bi-trash` | Cancella |
| `bi-plus-circle` | Nuovo / aggiungi |
| `bi-arrow-right` | Avanti / dettagli |
| `bi-arrow-left` | Indietro |
| `bi-search` | Filtra |
| `bi-info-circle` | Nota informativa |
| `bi-person` / `bi-lock` | Login fields |
| `bi-building` / `bi-briefcase` | SubCdc / Codice Funzione |
| `bi-person-fill-exclamation` | Banner "per conto di" |

## Layout patterns

### Page shell
```
[navbar logo+brand | nav-links | lang-selector | user+logout]
[main container (flex-grow-1, pb-5)]
  [flash messages (dismissible)]
  [h2 page title (border-bottom)]
  [content cards / tables / forms]
[footer (sticky, logo small + tagline)]
```

### Form pattern (es. nuova dichiarazione)
```
[h2 page title]
[card grigia con info contestuali (read-only)]
[form post enctype=multipart]
  [radio gruppo]
  [input number/text/date]
  [conditional section per TAXI]
  [file input multipli]
  [amount preview live]
  [primary CTA + secondary action + link annulla]
```

### Table pattern (es. lista dichiarazioni)
```
[h2 + bottone "Nuova"]
[table table-striped]
  [thead navy bg]
  [tbody con badges, importo formato, link Dettagli]
[empty state: alert info "Nessun..."]
```

### Detail pattern (es. view dichiarazione)
```
[h2 con badge stato inline]
[card con tabella dati read-only]
[h4 sezione Documenti]
[list-group con icone + bottone Scarica]
[actions row: edit form inline (if can_edit) + delete + admin override]
```

## Motion

- Card hover: `transition: box-shadow 0.2s ease-in-out`
- Form focus: nessuna transition esplicita (Bootstrap default)
- Alert dismiss: Bootstrap fade (250ms)
- No motion design custom; eviteremo skew, parallax, jitter

## Responsive

- Breakpoint default Bootstrap (sm 576, md 768, lg 992, xl 1200)
- Navbar: `navbar-expand-lg` (collassa sotto 992px)
- Cards dashboard: `col-md-4` (3 columns desktop, 1 column mobile)
- Map container: 500px desktop, ridotta su mobile (TODO: aggiungere media query)
- Tables: scroll orizzontale se necessario (Bootstrap `table-responsive` da aggiungere)

## A11y

- Lang attribute: `<html lang="it">` (TODO: render dinamico based on locale)
- ARIA labels su button-only (logout, lang-selector)
- Focus ring: visibile via `:focus`
- Color contrast: WCAG AA garantito (navy su bianco = 11.5:1)
- Form labels: `for=` esplicito
- Confirm dialogs: nativi browser (semplice, accessibile)

## Areas to improve (audit candidates)

- **Heading hierarchy**: alcune pagine partono da h2 senza h1 prima
- **Skip-to-content link**: assente
- **SRI sui CDN**: Bootstrap CSS/JS senza `integrity=` (supply chain)
- **Map responsive**: 500px fissi anche su mobile (sproporzionato)
- **Dark mode**: non implementato (intenzionale per scope)
- **Loading states**: form submit non mostra spinner
- **Empty states**: testuali, potrebbero avere illustrazione minimal
- **Pagination**: storico admin non paginato (V2)
