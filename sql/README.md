# Script SQL — Fogli di Percorso

Script DDL da eseguire manualmente in SQL Server Management Studio (SSMS)
con un utente che ha permessi `db_ddladmin` su `Employee` e in particolare
sullo schema `fdp`.

## Ordine di esecuzione

1. `001_init.sql` — ALTER tabelle esistenti + CREATE `PathTrackReimbursementRates` + INDICI
2. `002_add_status.sql` — workflow DRAFT/SUBMITTED (aggiunge `Status` e `SubmittedOn` a `PathTracks`)
3. `004_create_bnrrates.sql` — tabella `BnrRates` (tassi EUR->RON) + colonna `BnrRateRonPerEur` su `PathTracks`
4. `005_fix_bnrrates_schema.sql` — fix typo `Ratesid`→`RateId` e aggiunta colonna `DateSys` (solo se la tabella era stata creata manualmente con schema diverso da 004)

Gli script sono idempotenti: si possono rieseguire senza danni.

## Note sui numeri di migrazione

La migrazione `003_*` non esiste (era prevista per una FK ma rimandata).
Si passa da 002 a 004 direttamente. Mantenere i numeri come riferimento storico.

## Dopo l'esecuzione di 001

Inserire la prima riga di rate:

```sql
INSERT INTO Employee.fdp.PathTrackReimbursementRates
    (AvgConsumptionKmL, AvgFuelPriceEurL, ValidFrom, ValidTo, UserSys)
VALUES
    (15.00, 1.700, '2026-01-01', NULL, SUSER_SNAME());
```
