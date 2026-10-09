-- Preserve existing logins so active Power BI and SSMS sessions are not interrupted.
-- Run in SSMS with SQLCMD Mode enabled and define both password variables locally.
-- Do not put real passwords in this file or commit them.
USE master;
GO
IF SUSER_ID(N'qa_etl') IS NULL
    CREATE LOGIN qa_etl WITH PASSWORD = '$(qa_etl_password)';
IF SUSER_ID(N'qa_powerbi') IS NULL
    CREATE LOGIN qa_powerbi WITH PASSWORD = '$(qa_powerbi_password)';
GO

-- Existing login passwords are left unchanged; SQLCMD values are used only when
-- a login must be created.
USE QualityAnalytics;
GO
IF DATABASE_PRINCIPAL_ID(N'qa_etl') IS NULL
    CREATE USER qa_etl FOR LOGIN qa_etl;
IF DATABASE_PRINCIPAL_ID(N'qa_powerbi') IS NULL
    CREATE USER qa_powerbi FOR LOGIN qa_powerbi;
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members
    WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N'db_datareader')
      AND member_principal_id = DATABASE_PRINCIPAL_ID(N'qa_etl')
)
    ALTER ROLE db_datareader ADD MEMBER qa_etl;
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members
    WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N'db_datawriter')
      AND member_principal_id = DATABASE_PRINCIPAL_ID(N'qa_etl')
)
    ALTER ROLE db_datawriter ADD MEMBER qa_etl;
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members
    WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N'db_datareader')
      AND member_principal_id = DATABASE_PRINCIPAL_ID(N'qa_powerbi')
)
    ALTER ROLE db_datareader ADD MEMBER qa_powerbi;
GO