# Script SQL — Fogli di Percorso

Script DDL da eseguire manualmente in SQL Server Management Studio (SSMS)
con un utente che ha permessi `db_ddladmin` su `Employee` e in particolare
sullo schema `fdp`.

## Ordine di esecuzione

1. `001_init.sql` — ALTER tabelle esistenti + CREATE `PathTrackReimbursementRates` + INDICI
2. `002_add_status.sql` — workflow DRAFT/SUBMITTED (aggiunge `Status` e `SubmittedOn` a `PathTracks`)

Gli script sono idempotenti: si possono rieseguire senza danni.

## Dopo l'esecuzione di 001

Inserire la prima riga di rate:

```sql
INSERT INTO Employee.fdp.PathTrackReimbursementRates
    (AvgConsumptionKmL, AvgFuelPriceEurL, ValidFrom, ValidTo, UserSys)
VALUES
    (15.00, 1.700, '2026-01-01', NULL, SUSER_SNAME());
```
