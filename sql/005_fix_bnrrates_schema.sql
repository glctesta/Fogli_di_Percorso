-- =====================================================================
-- Fogli di Percorso - Migrazione 005: fix schema BnrRates
-- Eseguire UNA SOLA VOLTA in SSMS con permessi DDL su Employee.fdp.
-- Idempotente: riesecuzioni successive sono no-op.
--
-- Contesto: in alcuni ambienti la tabella fdp.BnrRates era stata creata
-- manualmente con la colonna "Ratesid" (typo) anziche' "RateId", e priva
-- della colonna DateSys. Questo script ripristina lo schema canonico
-- definito in 004_create_bnrrates.sql.
-- =====================================================================

USE Employee;
GO

-- ---------------------------------------------------------------------
-- 1. Rename Ratesid -> RateId (se necessario)
-- ---------------------------------------------------------------------
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Object_ID = Object_ID(N'fdp.BnrRates')
      AND Name = N'Ratesid'
)
AND NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Object_ID = Object_ID(N'fdp.BnrRates')
      AND Name = N'RateId'
)
BEGIN
    EXEC sp_rename N'fdp.BnrRates.Ratesid', N'RateId', N'COLUMN';
    PRINT '  - Colonna Ratesid rinominata in RateId';
END
ELSE
BEGIN
    PRINT '  - Rename non necessario (RateId gia presente o Ratesid assente)';
END
GO

-- ---------------------------------------------------------------------
-- 2. Aggiungi colonna DateSys se mancante
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Object_ID = Object_ID(N'fdp.BnrRates')
      AND Name = N'DateSys'
)
BEGIN
    ALTER TABLE fdp.BnrRates
        ADD DateSys DATETIME NOT NULL
        CONSTRAINT DF_BnrRates_DateSys DEFAULT GETDATE();
    PRINT '  - Colonna DateSys aggiunta';
END
ELSE
BEGIN
    PRINT '  - DateSys gia presente';
END
GO

PRINT 'Migrazione 005_fix_bnrrates_schema.sql completata.';
