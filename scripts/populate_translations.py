"""Populate RO and EN translation files from the glossary."""
import re
import sys

# Translation glossary: it_msgid -> (ro_msgstr, en_msgstr)
translations = {
    "Accedi": ("Autentificare", "Sign in"),
    "Esci": ("Iesire", "Logout"),
    "Esci dall'applicazione": ("Iesire din aplicatie", "Sign out"),
    "Nome utente": ("Utilizator", "Username"),
    "Password": ("Parola", "Password"),
    "Entra": ("Intra", "Enter"),
    "Home": ("Acasa", "Home"),
    "Punto di partenza": ("Punct de plecare", "Starting point"),
    "Dichiarazioni": ("Declaratii", "Declarations"),
    "Amministrazione": ("Administrare", "Administration"),
    "gestione rimborsi carburante e taxi": ("gestionare rambursari carburant si taxi", "fuel and taxi reimbursement management"),
    "Benvenuto, %(name)s": ("Bun venit, %(name)s", "Welcome, %(name)s"),
    "SubCdc:": ("SubCdc:", "SubCdc:"),
    "Codice Funzione:": ("Cod functie:", "Function code:"),
    "Definisci o aggiorna il tuo punto di partenza sulla mappa.": ("Defineste sau actualizeaza punctul de plecare pe harta.", "Define or update your starting point on the map."),
    "Vai alla mappa": ("Mergi la harta", "Go to map"),
    "Inserisci viaggi, carica i PDF e calcola il rimborso.": ("Introduce calatorii, incarca PDF-urile si calculeaza rambursarea.", "Enter trips, upload PDFs and calculate the reimbursement."),
    "Vai alle dichiarazioni": ("Mergi la declaratii", "Go to declarations"),
    "Rappresenta colleghi e consulta lo storico.": ("Reprezinta colegi si consulta istoricul.", "Represent colleagues and view history."),
    "Vai all'area admin": ("Mergi la zona admin", "Go to admin area"),
    "Accesso negato": ("Acces refuzat", "Access denied"),
    "Non hai i permessi per accedere a questa pagina.": ("Nu ai permisiunea de a accesa aceasta pagina.", "You do not have permission to access this page."),
    "Torna alla home": ("Inapoi la pagina principala", "Back to home"),
    "Pagina non trovata": ("Pagina nu a fost gasita", "Page not found"),
    "L'indirizzo richiesto non esiste.": ("Adresa solicitata nu exista.", "The requested address does not exist."),
    "Errore interno": ("Eroare interna", "Internal error"),
    "Errore interno del server": ("Eroare interna a serverului", "Internal server error"),
    "Si e' verificato un errore imprevisto. L'amministratore e' stato informato.": ("A aparut o eroare neasteptata. Administratorul a fost informat.", "An unexpected error occurred. The administrator has been notified."),
    "Credenziali non valide.": ("Credentiale invalide.", "Invalid credentials."),
    "Troppi tentativi falliti, riprovare piu' tardi.": ("Prea multe incercari esuate, reincearca mai tarziu.", "Too many failed attempts, please try again later."),
    "Nuova dichiarazione": ("Declaratie noua", "New declaration"),
    "Dichiarazione - %(month)s %(year)s": ("Declaratie - %(month)s %(year)s", "Declaration - %(month)s %(year)s"),
    "Tipo rimborso": ("Tip rambursare", "Reimbursement type"),
    "Carburante": ("Carburant", "Fuel"),
    "Taxi": ("Taxi", "Taxi"),
    "Numero viaggi (A/R)": ("Numar calatorii (Dus/Intors)", "Number of trips (round-trip)"),
    "Il sistema considera ogni viaggio come andata + ritorno.": ("Sistemul considera fiecare calatorie ca dus + intors.", "The system counts each trip as outbound + return."),
    "Importi ricevute (€)": ("Sume chitante (€)", "Receipt amounts (€)"),
    "+ Aggiungi ricevuta": ("+ Adauga chitanta", "+ Add receipt"),
    "Foglio di percorso (PDF, max 5 MB)": ("Fisa de traseu (PDF, max 5 MB)", "Travel sheet (PDF, max 5 MB)"),
    "Ricevute (PDF, max 5 MB ciascuna)": ("Chitante (PDF, max 5 MB fiecare)", "Receipts (PDF, max 5 MB each)"),
    "Anteprima rimborso:": ("Previzualizare rambursare:", "Reimbursement preview:"),
    "Salva bozza": ("Salveaza ciorna", "Save draft"),
    "Salva e invia": ("Salveaza si trimite", "Save and submit"),
    "Conferma e invia": ("Confirma si trimite", "Confirm and submit"),
    "Cancella bozza": ("Sterge ciorna", "Delete draft"),
    "Aggiorna bozza": ("Actualizeaza ciorna", "Update draft"),
    "Invia (override admin)": ("Trimite (override admin)", "Submit (admin override)"),
    "Annulla": ("Anuleaza", "Cancel"),
    "BOZZA": ("CIORNA", "DRAFT"),
    "INVIATA": ("TRIMISA", "SUBMITTED"),
    "BOZZA modificabile": ("CIORNA editabila", "Editable DRAFT"),
    "Stato": ("Stare", "Status"),
    "Numero registro": ("Numar registru", "Registry number"),
    "Inviata il": ("Trimisa pe", "Submitted on"),
    "Numero viaggi A/R": ("Numar calatorii dus/intors", "Trips (round-trip)"),
    "Distanza one-way": ("Distanta dus", "One-way distance"),
    "Totale taxi (ricevute)": ("Total taxi (chitante)", "Taxi total (receipts)"),
    "Importo rimborso": ("Suma rambursare", "Reimbursement amount"),
    "Documenti": ("Documente", "Documents"),
    "Documenti caricati": ("Documente incarcate", "Uploaded documents"),
    "Scarica": ("Descarca", "Download"),
    "Modifica bozza": ("Modifica ciorna", "Edit draft"),
    "Le mie dichiarazioni": ("Declaratiile mele", "My declarations"),
    "Mese": ("Luna", "Month"),
    "Tipo": ("Tip", "Type"),
    "Viaggi A/R": ("Calatorii Dus/Intors", "Round trips"),
    "Importo": ("Suma", "Amount"),
    "N. registro": ("Nr. registru", "Registry no."),
    "Dettagli": ("Detalii", "Details"),
    "Nessuna dichiarazione presente.": ("Nicio declaratie prezenta.", "No declarations."),
    "Torna alla lista": ("Inapoi la lista", "Back to list"),
    "Dipendenti rappresentabili": ("Angajati reprezentabili", "Representable employees"),
    "Mappa": ("Harta", "Map"),
    "Dipendente": ("Angajat", "Employee"),
    "FC": ("FC", "FC"),
    "Azioni": ("Actiuni", "Actions"),
    "Nessun collega rappresentabile per il tuo SubCdc.": ("Niciun coleg reprezentabil pentru SubCdc-ul tau.", "No representable colleagues for your SubCdc."),
    "Storico dichiarazioni SubCdc": ("Istoric declaratii SubCdc", "SubCdc declarations history"),
    "Anno": ("An", "Year"),
    "Tutti": ("Toate", "All"),
    "Filtra": ("Filtreaza", "Filter"),
    "Export XLSX": ("Export XLSX", "Export XLSX"),
    "Nessuna dichiarazione trovata con i filtri selezionati.": ("Nicio declaratie gasita cu filtrele selectate.", "No declarations found with the selected filters."),
    "Torna ai rappresentati": ("Inapoi la reprezentati", "Back to representable"),
    "Definisci o aggiorna il tuo punto di partenza": ("Defineste sau actualizeaza punctul de plecare", "Define or update your starting point"),
    "Coordinate:": ("Coordonate:", "Coordinates:"),
    "Distanza stradale verso la sede:": ("Distanta rutiera catre sediu:", "Road distance to the office:"),
    "Cancella punto": ("Sterge punctul", "Delete point"),
    "Cancellare il punto di partenza?": ("Stergeti punctul de plecare?", "Delete starting point?"),
    'Etichetta (es. "Casa", "Via Roma 5")': ('Eticheta (ex. "Acasa", "Strada X 5")', 'Label (e.g. "Home", "Roma St. 5")'),
    "Coordinate selezionate:": ("Coordonate selectate:", "Selected coordinates:"),
    "Indirizzo (auto):": ("Adresa (auto):", "Address (auto):"),
    "Salva punto di partenza": ("Salveaza punctul de plecare", "Save starting point"),
    "Nessun punto attivo. Clicca sulla mappa per scegliere il tuo punto di partenza.": ("Niciun punct activ. Click pe harta pentru a alege punctul de plecare.", "No active point. Click on the map to choose your starting point."),
    "Bozza salvata. La potrai aggiornare fino al 5 del mese successivo.": ("Ciorna salvata. O poti actualiza pana la data de 5 a lunii urmatoare.", "Draft saved. You can update it until the 5th of the next month."),
    "Bozza aggiornata.": ("Ciorna actualizata.", "Draft updated."),
    "Bozza cancellata.": ("Ciorna stearsa.", "Draft deleted."),
    "Definisci prima il punto di partenza nella mappa.": ("Defineste mai intai punctul de plecare pe harta.", "Please define the starting point on the map first."),
    "Periodo di inserimento chiuso.": ("Perioada de introducere inchisa.", "Submission period closed."),
    "Tipo rimborso non valido.": ("Tip rambursare invalid.", "Invalid reimbursement type."),
    "Numero viaggi non valido.": ("Numar calatorii invalid.", "Invalid number of trips."),
    "Foglio di percorso (PDF) obbligatorio.": ("Fisa de traseu (PDF) obligatorie.", "Travel sheet (PDF) required."),
    "Foglio di percorso troppo grande (max 5 MB).": ("Fisa de traseu prea mare (max 5 MB).", "Travel sheet too large (max 5 MB)."),
    "Il foglio di percorso non e' un PDF valido.": ("Fisa de traseu nu este un PDF valid.", "Travel sheet is not a valid PDF."),
    "Almeno una ricevuta (PDF) obbligatoria.": ("Cel putin o chitanta (PDF) obligatorie.", "At least one receipt (PDF) required."),
    "Importi ricevute non validi.": ("Sume chitante invalide.", "Invalid receipt amounts."),
    "Esiste gia' una dichiarazione attiva per il mese.": ("Exista deja o declaratie activa pentru aceasta luna.", "An active declaration already exists for this month."),
    "Rate non configurato per il mese. Contattare l'amministratore.": ("Tarif neconfigurat pentru aceasta luna. Contactati administratorul.", "Rate not configured for the month. Please contact the administrator."),
    "Servizio mappe temporaneamente non disponibile. Riprovare piu' tardi.": ("Serviciu de harti temporar indisponibil. Reincercati mai tarziu.", "Map service temporarily unavailable. Please try again later."),
    "Punto di partenza salvato.": ("Punctul de plecare salvat.", "Starting point saved."),
    "Punto di partenza cancellato.": ("Punctul de plecare sters.", "Starting point deleted."),
    "Coordinate non valide.": ("Coordonate invalide.", "Invalid coordinates."),
    "Coordinate non valide (lat/lon fuori range).": ("Coordonate invalide (lat/lon in afara intervalului).", "Invalid coordinates (lat/lon out of range)."),
    "Etichetta obbligatoria.": ("Eticheta obligatorie.", "Label is required."),
    "Esiste gia' un punto attivo. Cancellarlo prima di crearne uno nuovo.": ("Exista deja un punct activ. Sterge-l inainte de a crea unul nou.", "An active point already exists. Delete it before creating a new one."),
    "Punto non trovato o non posseduto.": ("Punct negasit sau neposedat.", "Point not found or not owned."),
    "Identificativo punto non valido.": ("Identificator punct invalid.", "Invalid point identifier."),
    "Dichiarazione inviata con successo. RegistryId: %(rid)s": ("Declaratie trimisa cu succes. Nr. registru: %(rid)s", "Declaration submitted successfully. Registry: %(rid)s"),
    "Bozza salvata ma non inviata: %(error)s. Potrai inviarla dal 1 al 5 del mese successivo.": ("Ciorna salvata dar netrimisa: %(error)s. O poti trimite intre 1 si 5 ale lunii urmatoare.", "Draft saved but not submitted: %(error)s. You can submit it between the 1st and the 5th of next month."),
    "Solo le bozze possono essere cancellate.": ("Numai ciornele pot fi sterse.", "Only drafts can be deleted."),
    "Impossibile cancellare (non e' una bozza o gia' cancellata).": ("Imposibil de sters (nu este o ciorna sau este deja stearsa).", "Cannot delete (not a draft or already deleted)."),
    "Confermi l'invio definitivo? Dopo l'invio non potrai ù modificare.": ("Confirmati trimiterea definitiva? Dupa trimitere nu veti mai putea modifica.", "Confirm final submission? After submitting you cannot modify it anymore."),
    "Confermi l'invio definitivo? Dopo l'invio non potrai più modificare.": ("Confirmati trimiterea definitiva? Dupa trimitere nu veti mai putea modifica.", "Confirm final submission? After submitting you cannot modify it anymore."),
    "Cancellare la bozza?": ("Stergeti ciorna?", "Delete draft?"),
    "Invio admin in override scadenza. Confermi?": ("Trimitere admin in override scadenta. Confirmati?", "Admin override submission. Confirm?"),
    "Periodo di modifica chiuso.": ("Perioada de modificare inchisa.", "Modification period closed."),
    "Dichiarazione gia' inviata: nessuna modifica possibile.": ("Declaratie deja trimisa: nicio modificare posibila.", "Declaration already submitted: no modification possible."),
    "Azione non riconosciuta.": ("Actiune nerecunoscuta.", "Action not recognized."),
    "Punto di partenza:": ("Punct de plecare:", "Starting point:"),
    "Distanza one-way:": ("Distanta dus:", "One-way distance:"),
    "Menu di navigazione": ("Navigare", "Navigation menu"),
    "Chiudi": ("Inchide", "Close"),
    "Ricevuta '%(filename)s' troppo grande (max 5 MB).": ("Chitanta '%(filename)s' prea mare (max 5 MB).", "Receipt '%(filename)s' too large (max 5 MB)."),
    "L'invio sara' possibile solo dal 1 al 5 del mese successivo.": ("Trimiterea va fi posibila doar intre 1 si 5 ale lunii urmatoare.", "Submission will only be possible between the 1st and 5th of the following month."),
    "disponibile dal 1 al 5 del mese successivo": ("disponibil intre 1 si 5 ale lunii urmatoare", "available from the 1st to 5th of the following month"),
    "Invio possibile solo dal 1 al 5 del mese successivo.": ("Trimiterea posibila doar intre 1 si 5 ale lunii urmatoare.", "Submission possible only between 1st and 5th of the next month."),
    "dal 1 al 5 del mese successivo": ("intre 1 si 5 ale lunii urmatoare", "from 1st to 5th of the next month"),
    "Dichiarazione": ("Declaratie", "Declaration"),
    "Torna allo storico": ("Inapoi la istoric", "Back to history"),
    "Dichiarazione #%(id)s": ("Declaratie #%(id)s", "Declaration #%(id)s"),
    "Dichiarazione #%(id)s": ("Declaratie #%(id)s", "Declaration #%(id)s"),
}


def get_msgid_value(lines, start_idx):
    """Extract full msgid string (handles multiline) starting from the msgid line."""
    line = lines[start_idx]
    if line == 'msgid ""':
        # Multiline: collect continuation lines
        result = ""
        i = start_idx + 1
        while i < len(lines) and lines[i].startswith('"'):
            result += lines[i][1:-1]  # strip surrounding quotes
            i += 1
        return result, i
    else:
        # Single line: msgid "value"
        return line[7:-1], start_idx + 1  # strip 'msgid "' and '"'


def populate_po(src_path, lang_idx):
    """lang_idx: 0=ro, 1=en"""
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("msgid ") and line != 'msgid ""':
            # Single-line msgid
            msgid_val = line[7:-1]  # strip 'msgid "' and '"'
            out.append(line)
            i += 1
            # Check next line for msgstr
            if i < len(lines) and lines[i].startswith('msgstr ""'):
                translation = translations.get(msgid_val)
                if translation:
                    out.append('msgstr "' + translation[lang_idx] + '"')
                else:
                    # Fallback: keep empty or use msgid
                    out.append('msgstr "' + msgid_val + '"')
                i += 1
                continue
            continue
        elif line == 'msgid ""':
            # Could be header (preceded by blank/comment) or multiline
            # Check if the next line starts with '"' (continuation)
            if i + 1 < len(lines) and lines[i + 1].startswith('"'):
                # Multiline msgid
                msgid_parts = []
                out.append(line)
                i += 1
                while i < len(lines) and lines[i].startswith('"'):
                    msgid_parts.append(lines[i][1:-1])
                    out.append(lines[i])
                    i += 1
                full_msgid = "".join(msgid_parts)
                # Now expect msgstr
                if i < len(lines) and lines[i].startswith('msgstr ""'):
                    translation = translations.get(full_msgid)
                    if translation:
                        out.append('msgstr "' + translation[lang_idx] + '"')
                    else:
                        out.append('msgstr "' + full_msgid + '"')
                    i += 1
                    continue
                continue
            else:
                # Header empty msgid
                out.append(line)
        else:
            out.append(line)
        i += 1

    with open(src_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print(f"Populated {src_path}")


if __name__ == "__main__":
    populate_po("fdp_app/translations/ro/LC_MESSAGES/messages.po", 0)
    populate_po("fdp_app/translations/en/LC_MESSAGES/messages.po", 1)
    print("Done.")
