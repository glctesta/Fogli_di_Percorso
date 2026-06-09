-- =====================================================================
-- Fogli di Percorso - Migrazione 006: token di reset password
-- Eseguire UNA SOLA VOLTA in SSMS con permessi DDL su Employee.fdp
-- Idempotente: riesecuzioni successive sono no-op.
--
-- Nota di sicurezza: si memorizza SOLO l'hash SHA-256 del token (TokenHash),
-- mai il token in chiaro. Il token in chiaro vive solo nel link email.
-- =====================================================================

USE Employee;
GO

-- ---------------------------------------------------------------------
-- 1. CREATE TABLE: PasswordResetTokens
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.tables
    WHERE Name = N'PasswordResetTokens'
      AND SCHEMA_NAME(schema_id) = N'fdp'
)
BEGIN
    CREATE TABLE fdp.PasswordResetTokens (
        TokenId        INT IDENTITY(1,1) PRIMARY KEY,
        NomeUser       NVARCHAR(100) NOT NULL,   -- username (chiave in resetservices.tbuserkey)
        TokenHash      CHAR(64)      NOT NULL,   -- SHA-256 esadecimale del token
        ExpiresAt      DATETIME      NOT NULL,
        UsedAt         DATETIME      NULL,        -- valorizzato al consumo (uso singolo)
        RequestIp      NVARCHAR(45)  NULL,        -- IPv4/IPv6 del richiedente (audit)
        DateSys        DATETIME      NOT NULL CONSTRAINT DF_PwdResetTokens_DateSys DEFAULT GETDATE()
    );
END
GO

-- ---------------------------------------------------------------------
-- 2. Indice per lookup veloce sul TokenHash (validazione del link)
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PwdResetTokens_TokenHash'
      AND object_id = OBJECT_ID(N'fdp.PasswordResetTokens')
)
BEGIN
    CREATE UNIQUE INDEX IX_PwdResetTokens_TokenHash
        ON fdp.PasswordResetTokens(TokenHash);
END
GO

-- ---------------------------------------------------------------------
-- 3. Indice per invalidare i token aperti di un utente
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PwdResetTokens_NomeUser'
      AND object_id = OBJECT_ID(N'fdp.PasswordResetTokens')
)
BEGIN
    CREATE INDEX IX_PwdResetTokens_NomeUser
        ON fdp.PasswordResetTokens(NomeUser)
        WHERE UsedAt IS NULL;
END
GO

PRINT 'Migrazione 006_create_password_reset_tokens.sql completata.';
