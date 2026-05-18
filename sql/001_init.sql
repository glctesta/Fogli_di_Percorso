-- =====================================================================
-- Fogli di Percorso - Migrazione iniziale
-- Eseguire UNA SOLA VOLTA in SQL Server Management Studio
-- come utente con permessi DDL su Employee.fdp
-- =====================================================================

USE Employee;
GO

-- ---------------------------------------------------------------------
-- 1. ALTER TABLE: PathTrackCoordinates
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'RoadKmToWorkplace'
      AND Object_ID = Object_ID(N'fdp.PathTrackCoordinates')
)
BEGIN
    ALTER TABLE fdp.PathTrackCoordinates
        ADD RoadKmToWorkplace DECIMAL(9,3) NULL;
END
GO

-- ---------------------------------------------------------------------
-- 2. ALTER TABLE: PathTrackDocs
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'DateOut'
      AND Object_ID = Object_ID(N'fdp.PathTrackDocs')
)
BEGIN
    ALTER TABLE fdp.PathTrackDocs
        ADD DateOut DATETIME NULL;
END
GO

-- ---------------------------------------------------------------------
-- 3. ALTER TABLE: PathTracks - colonne di calcolo congelato e soft-delete
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'ReimbursementType'
      AND Object_ID = Object_ID(N'fdp.PathTracks')
)
BEGIN
    ALTER TABLE fdp.PathTracks
        ADD ReimbursementType  CHAR(10)     NULL,
            NumberOfTrips      INT          NULL,
            RoadKm             DECIMAL(9,3) NULL,
            RateIdUsed         INT          NULL,
            TaxiTotalEur       DECIMAL(9,2) NULL,
            ComputedAmountEur  DECIMAL(9,2) NULL,
            DateOut            DATETIME     NULL;
END
GO

-- NOTA: le colonne sono NULL per non rompere eventuali dati esistenti.
-- L'applicazione le valorizzera' sempre per i nuovi record.
-- L'integrita' e' garantita lato app (vedi sezione 7.2 della spec).

-- ---------------------------------------------------------------------
-- 4. CREATE TABLE: PathTrackReimbursementRates
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.tables
    WHERE Name = N'PathTrackReimbursementRates'
      AND SCHEMA_NAME(schema_id) = N'fdp'
)
BEGIN
    CREATE TABLE fdp.PathTrackReimbursementRates (
        RateId              INT IDENTITY(1,1) PRIMARY KEY,
        AvgConsumptionKmL   DECIMAL(6,2) NOT NULL,
        AvgFuelPriceEurL    DECIMAL(6,3) NOT NULL,
        ValidFrom           DATE NOT NULL,
        ValidTo             DATE NULL,
        DateSys             DATETIME NOT NULL DEFAULT GETDATE(),
        UserSys             NVARCHAR(100) NOT NULL
    );

    CREATE UNIQUE INDEX UX_Rates_ValidFrom
        ON fdp.PathTrackReimbursementRates(ValidFrom);
END
GO

-- ---------------------------------------------------------------------
-- 5. INDICI di supporto
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PathTrackCoordinates_Emp_Out'
      AND object_id = OBJECT_ID(N'fdp.PathTrackCoordinates')
)
BEGIN
    CREATE INDEX IX_PathTrackCoordinates_Emp_Out
        ON fdp.PathTrackCoordinates (EmployeerHireHistoryId, DateOut);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PathTracks_Emp_Date'
      AND object_id = OBJECT_ID(N'fdp.PathTracks')
)
BEGIN
    CREATE INDEX IX_PathTracks_Emp_Date
        ON fdp.PathTracks (EmployeeHireHistoryId, DatePathTrack)
        WHERE DateOut IS NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PathTracks_Behalf_Date'
      AND object_id = OBJECT_ID(N'fdp.PathTracks')
)
BEGIN
    CREATE INDEX IX_PathTracks_Behalf_Date
        ON fdp.PathTracks (InBehalfOfId, DatePathTrack)
        WHERE DateOut IS NULL AND InBehalfOfId IS NOT NULL;
END
GO

PRINT 'Migrazione 001_init.sql completata.';
