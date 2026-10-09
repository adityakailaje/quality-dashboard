USE QualityAnalytics;
GO

-- Drop tables in order of foreign key dependencies
DROP TABLE IF EXISTS dbo.FactInspection;
DROP TABLE IF EXISTS dbo.SPCEvents;
DROP TABLE IF EXISTS dbo.RawInspection;
DROP TABLE IF EXISTS dbo.SPCLimits;
DROP TABLE IF EXISTS dbo.ETL_Log;
DROP TABLE IF EXISTS dbo.DimShift;
DROP TABLE IF EXISTS dbo.DimDate;
DROP TABLE IF EXISTS dbo.DimMachine;
DROP TABLE IF EXISTS dbo.DimSupplier;
DROP TABLE IF EXISTS dbo.DimDefectType;
GO