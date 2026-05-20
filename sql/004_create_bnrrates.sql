-- =====================================================================
-- Fogli di Percorso - Migrazione 004: tassi BNR EUR -> RON
-- Eseguire UNA SOLA VOLTA in SSMS con permessi DDL su Employee.fdp
-- Idempotente: riesecuzioni successive sono no-op.
-- =====================================================================

USE Employee;
GO

-- ---------------------------------------------------------------------
-- 1. CREATE TABLE: BnrRates
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.tables
    WHERE Name = N'BnrRates'
      AND SCHEMA_NAME(schema_id) = N'fdp'
)
BEGIN
    CREATE TABLE fdp.BnrRates (
        RateId              INT IDENTITY(1,1) PRIMARY KEY,
        RateValueRonPerEur  DECIMAL(10,6) NOT NULL,
        Source              CHAR(10) NOT NULL,  -- 'STANDARD' | 'BNR' | 'CURSBNR' | 'MANUAL'
        ValidFrom           DATE NOT NULL,
        ValidTo             DATE NULL,
        IsStandard          BIT NOT NULL CONSTRAINT DF_BnrRates_IsStandard DEFAULT 0,
        DateSys             DATETIME NOT NULL CONSTRAINT DF_BnrRates_DateSys DEFAULT GETDATE(),
        UserSys             NVARCHAR(100) NOT NULL
    );
END
GO

-- ---------------------------------------------------------------------
-- 2. Indice per lookup per data
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_BnrRates_ValidFrom'
      AND object_id = OBJECT_ID(N'fdp.BnrRates')
)
BEGIN
    CREATE INDEX IX_BnrRates_ValidFrom
        ON fdp.BnrRates(ValidFrom);
END
GO

-- ---------------------------------------------------------------------
-- 3. Indice per lookup standard rates
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_BnrRates_Standard'
      AND object_id = OBJECT_ID(N'fdp.BnrRates')
)
BEGIN
    CREATE INDEX IX_BnrRates_Standard
        ON fdp.BnrRates(IsStandard, ValidFrom)
        WHERE IsStandard = 1;
END
GO

-- ---------------------------------------------------------------------
-- 4. ALTER fdp.PathTracks: aggiungi colonna BnrRateRonPerEur
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'BnrRateRonPerEur'
      AND Object_ID = Object_ID(N'fdp.PathTracks')
)
BEGIN
    ALTER TABLE fdp.PathTracks
        ADD BnrRateRonPerEur DECIMAL(10,6) NULL;
END
GO

PRINT 'Migrazione 004_create_bnrrates.sql completata.';
