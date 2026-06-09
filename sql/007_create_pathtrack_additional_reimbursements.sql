CREATE TABLE Employee.fdp.PathTrackAdditionalReimbursements (
    AdjustmentId         INT IDENTITY(1,1) PRIMARY KEY,
    EmployeeHireHistoryId INT NOT NULL,
    SubCdcId             INT NOT NULL,
    YearRef              INT NOT NULL,
    MonthRef             INT NOT NULL,
    AdditionalAmountEur  DECIMAL(9,2) NOT NULL DEFAULT 0,
    DeductionAmountEur   DECIMAL(9,2) NOT NULL DEFAULT 0,
    Notes                NVARCHAR(500) NULL,
    UserSys              NVARCHAR(100) NOT NULL,
    DateOut              DATETIME NULL,
    DateSys              DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE UNIQUE INDEX UX_PathTrackAdditionalReimbursements_PeriodEmployee
    ON Employee.fdp.PathTrackAdditionalReimbursements(EmployeeHireHistoryId, SubCdcId, YearRef, MonthRef)
    WHERE DateOut IS NULL;
