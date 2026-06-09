CREATE TABLE Employee.fdp.ReimbursementReportingPermissions (
    PermissionId    INT IDENTITY(1,1) PRIMARY KEY,
    PermissionType  VARCHAR(20) NOT NULL, -- USER | FUNCTION_CODE
    TargetValue     INT NOT NULL,
    Notes           NVARCHAR(255) NULL,
    UserSys         NVARCHAR(100) NOT NULL,
    DateOut         DATETIME NULL,
    DateSys         DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT CK_ReimbursementReportingPermissions_Type
        CHECK (PermissionType IN ('USER', 'FUNCTION_CODE'))
);

CREATE UNIQUE INDEX UX_ReimbursementReportingPermissions_Active
    ON Employee.fdp.ReimbursementReportingPermissions(PermissionType, TargetValue)
    WHERE DateOut IS NULL;
