# Fogli di Percorso

> Web app interna per la gestione mensile dei rimborsi spese carburante e taxi
> dei dipendenti Vandewiele Romania (sede Ghiroda, Calea Aviatorilor 4).

## Product

App Flask multi-lingua (RO default, IT, EN) e multi-valuta (EUR primario, RON
display via tasso BNR ufficiale). Ogni dipendente registra la propria
dichiarazione mensile, allega ricevute PDF, e — entro il 5 del mese successivo —
la conferma e invia ottenendo un numero di registro ufficiale dal sistema HR.

Workflow:
1. Setup punto di partenza sulla mappa (una volta)
2. Bozza mensile in qualsiasi momento (mese corrente o precedente non chiuso)
3. Modifica/cancellazione finché in stato `DRAFT`
4. Submit nella finestra 1-5 del mese successivo → consuma `RegistryId`,
   congela tasso BNR, immutable
5. Sistema HR esterno valorizza poi `ReceivedOn` per il pagamento

## Users

### Primario — dipendente in trasferta
- Età 25-60, qualunque livello tecnico
- Usa l'app **una volta al mese**, vuole finirla in 2-3 minuti
- Conosce poco di rimborsi normativi, si fida del calcolo automatico
- Non ricorda la procedura: la UI deve auto-guidare
- Lingua madre romeno, secondo lingua italiano o inglese

### Secondario — manager (FunctionCode > 60)
- Rappresenta colleghi (FC<60) dello stesso SubCdc
- Consulta storico mensile del proprio team
- Esporta XLSX per consegnare a HR/Payroll
- Può forzare invio bozze scadute (override admin)
- Vuole vedere "chi non ha ancora inviato" colpo d'occhio

### Terziario — admin tecnico
- Configura tasso BNR "standard" amministrativo
- Verifica log e statistiche
- Future: gestisce reminder email

## Voice & Brand

### Tone
- **Sobria, professionale**, niente esclamativi gratuiti
- **Multilingua**: romeno per default (sede in Romania); italiano per il
  committente Vandewiele Italia; inglese per workforce internazionale
- **Direct**: bottone "Salva e invia" non "Invia ora la tua bellissima dichiarazione!"
- Niente emoji nelle UI strings; emoji solo nelle bandiere lingua

### Brand
- **Logo VANDEWIELE ROMANIA** (16KB PNG, già in `static/img/logo.png`)
  - In navbar (su sfondo bianco per contrastare il navy)
  - In login card (grande, sopra il form)
  - In footer (piccolo, accompagnato dal tagline)
- **Tagline**: "gestione rimborsi carburante e taxi" / "gestionare rambursari
  carburant si taxi" / "fuel and taxi reimbursement management"

### Palette
- **Primario navy**: `#0b2a5b` (corporate, autorevolezza)
- **Primario dark hover**: `#07193b`
- **Accent ciano**: `#1d9bf0` (interattività, focus ring, link)
- **Background**: `#f5f7fb` (off-white morbido, riduce affaticamento)
- **Surface**: `#ffffff` (card, tabelle)
- **Border**: `#e3e7ef` (sottile, sempre)
- **Muted**: `#6b7280` (testo secondario)
- **Stati** (Bootstrap):
  - Successo: `#d1fae5` background, `#065f46` testo
  - Warning: `#fef3c7` / `#92400e`
  - Danger: `#fee2e2` / `#991b1b`
  - Info: `#dbeafe` / `#1e40af`

### Typography
- Stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- Heading: peso 600, colore navy
- Body: peso 400, colore `#1f2937`
- Form labels: peso 500

## Strategic Principles

### 1. Chiarezza prima della densità
L'utente compila in fretta una volta al mese. Le pagine devono essere
**scansionabili in 3 secondi**: stato, importo, prossima azione. Niente
muri di testo.

### 2. Stato sempre visibile
Ogni dichiarazione ha sempre un **badge di stato** ("BOZZA" giallo /
"INVIATA" verde). L'utente non deve mai chiedersi "è stata inviata?".

### 3. Calcolo trasparente
Importo mostrato come `€ 45.33 (RON 225.51 · tasso 4.9756)`. L'utente
vede sia EUR (interno) che RON (sede locale). Il tasso usato è esplicito
per audit.

### 4. Audit-friendly
Tutto storicizzato: `Status`, `SubmittedOn`, `RegistryId`, `BnrRateRonPerEur`
congelati al momento del submit. Soft-delete invece di hard delete.

### 5. Multi-language / multi-currency seamless
Cambio lingua dal dropdown navbar (cookie 1 anno). Tutte le UI strings
tradotte, niente testo orfano in italiano nei layout RO/EN.

### 6. Defensive validation
Magic bytes PDF, range lat/lon, finestre temporali, FK ownership.
L'utente non deve mai vedere uno stack trace.

## Anti-references

### Cosa NON vogliamo
- **Consumer-y / Stripe-look**: niente gradient psichedelici, blob illustrati,
  emoji-rich onboarding. Siamo un'app aziendale interna sobria.
- **Modali invadenti**: niente popup di "benvenuto", niente "scopri di più".
  La form si compila e basta.
- **Dark patterns**: niente bottoni rossi per cancellare bozza, niente
  confirm dialog ingannevoli.
- **Eccessivo skeumorfismo**: niente shadow esagerate, niente bordi spessi.
  Flat moderno con shadow soft.
- **Pseudo-AI**: niente "suggested category", niente "smart fill". L'utente
  sa cosa scrive.
- **Tracking / analytics terzi**: niente Google Analytics, niente pixel.
  È intranet, niente terze parti.
- **Dark mode**: non richiesto, non lo facciamo.
- **JavaScript framework**: niente React/Vue. Bootstrap + JS vanilla.

## Constraints tecnici

- **Stack**: Flask 3 + Jinja2 + Bootstrap 5.3 + Leaflet + JS vanilla
- **Deploy**: Waitress dietro IIS+TLS in produzione, dev server in test
- **Browser target**: Chrome/Edge moderni (target enterprise Vandewiele)
- **Offline-tolerant**: BNR/OSRM possono fallire, l'app continua
- **Performance**: pagina renderizzata <500ms server-side
- **A11y**: WCAG AA su contrasti, niente keyboard trap, label corrette
