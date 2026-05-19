-- =====================================================================
-- Fogli di Percorso - Migrazione 002: workflow DRAFT/SUBMITTED
-- Eseguire UNA SOLA VOLTA in SSMS con permessi DDL su Employee.fdp
-- Idempotente: riesecuzioni successive sono no-op.
-- =====================================================================

USE Employee;
GO

-- ---------------------------------------------------------------------
-- 1. Aggiunge Status e SubmittedOn a fdp.PathTracks
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'Status'
      AND Object_ID = Object_ID(N'fdp.PathTracks')
)
BEGIN
    ALTER TABLE fdp.PathTracks
        ADD Status      CHAR(10)  NOT NULL CONSTRAINT DF_PathTracks_Status DEFAULT 'DRAFT',
            SubmittedOn DATETIME  NULL;
END
GO

-- ---------------------------------------------------------------------
-- 2. Retro-compatibilita': i record con RegistryId esistente sono SUBMITTED
-- ---------------------------------------------------------------------
UPDATE fdp.PathTracks
SET Status = 'SUBMITTED',
    SubmittedOn = COALESCE(SubmittedOn, DateSys)
WHERE Status = 'DRAFT'
  AND RegistryId IS NOT NULL;
GO

-- ---------------------------------------------------------------------
-- 3. Indice per query "le mie bozze"
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PathTracks_Emp_Status'
      AND object_id = OBJECT_ID(N'fdp.PathTracks')
)
BEGIN
    CREATE INDEX IX_PathTracks_Emp_Status
        ON fdp.PathTracks (EmployeeHireHistoryId, Status)
        WHERE DateOut IS NULL;
END
GO

PRINT 'Migrazione 002_add_status.sql completata.';
