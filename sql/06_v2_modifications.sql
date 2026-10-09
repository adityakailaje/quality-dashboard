USE QualityAnalytics;
GO
/* Add operational, traceability, defect-count and cost fields. */
IF COL_LENGTH('dbo.RawInspection','production_order_id') IS NULL
 ALTER TABLE dbo.RawInspection ADD production_order_id VARCHAR(50) NULL;
IF COL_LENGTH('dbo.RawInspection','lot_id') IS NULL
 ALTER TABLE dbo.RawInspection ADD lot_id VARCHAR(50) NULL;
IF COL_LENGTH('dbo.RawInspection','product_family') IS NULL
 ALTER TABLE dbo.RawInspection ADD product_family VARCHAR(50) NULL;
IF COL_LENGTH('dbo.RawInspection','material_grade') IS NULL
 ALTER TABLE dbo.RawInspection ADD material_grade VARCHAR(30) NULL;
IF COL_LENGTH('dbo.RawInspection','material_thickness_mm') IS NULL
 ALTER TABLE dbo.RawInspection ADD material_thickness_mm DECIMAL(10,3) NULL;
IF COL_LENGTH('dbo.RawInspection','operator_id') IS NULL
 ALTER TABLE dbo.RawInspection ADD operator_id VARCHAR(30) NULL;
IF COL_LENGTH('dbo.RawInspection','defect_count') IS NULL
 ALTER TABLE dbo.RawInspection ADD defect_count INT NULL;
IF COL_LENGTH('dbo.RawInspection','defect_opportunities') IS NULL
 ALTER TABLE dbo.RawInspection ADD defect_opportunities INT NULL;
IF COL_LENGTH('dbo.RawInspection','rework_flag') IS NULL
 ALTER TABLE dbo.RawInspection ADD rework_flag BIT NULL;
IF COL_LENGTH('dbo.RawInspection','rework_minutes') IS NULL
 ALTER TABLE dbo.RawInspection ADD rework_minutes DECIMAL(10,2) NULL;
IF COL_LENGTH('dbo.RawInspection','cycle_time_sec') IS NULL
 ALTER TABLE dbo.RawInspection ADD cycle_time_sec DECIMAL(10,3) NULL;
IF COL_LENGTH('dbo.RawInspection','ideal_cycle_time_sec') IS NULL
 ALTER TABLE dbo.RawInspection ADD ideal_cycle_time_sec DECIMAL(10,3) NULL;
IF COL_LENGTH('dbo.RawInspection','unit_cost_inr') IS NULL
 ALTER TABLE dbo.RawInspection ADD unit_cost_inr DECIMAL(12,2) NULL;
IF COL_LENGTH('dbo.RawInspection','scrap_cost_inr') IS NULL
 ALTER TABLE dbo.RawInspection ADD scrap_cost_inr DECIMAL(12,2) NULL;
IF COL_LENGTH('dbo.RawInspection','rework_cost_inr') IS NULL
 ALTER TABLE dbo.RawInspection ADD rework_cost_inr DECIMAL(12,2) NULL;
IF COL_LENGTH('dbo.RawInspection','energy_kwh') IS NULL
 ALTER TABLE dbo.RawInspection ADD energy_kwh DECIMAL(12,5) NULL;
GO
IF COL_LENGTH('dbo.FactInspection','production_order_id') IS NULL
 ALTER TABLE dbo.FactInspection ADD production_order_id VARCHAR(50) NULL;
IF COL_LENGTH('dbo.FactInspection','lot_id') IS NULL
 ALTER TABLE dbo.FactInspection ADD lot_id VARCHAR(50) NULL;
IF COL_LENGTH('dbo.FactInspection','product_family') IS NULL
 ALTER TABLE dbo.FactInspection ADD product_family VARCHAR(50) NULL;
IF COL_LENGTH('dbo.FactInspection','material_grade') IS NULL
 ALTER TABLE dbo.FactInspection ADD material_grade VARCHAR(30) NULL;
IF COL_LENGTH('dbo.FactInspection','material_thickness_mm') IS NULL
 ALTER TABLE dbo.FactInspection ADD material_thickness_mm DECIMAL(10,3) NULL;
IF COL_LENGTH('dbo.FactInspection','operator_id') IS NULL
 ALTER TABLE dbo.FactInspection ADD operator_id VARCHAR(30) NULL;
IF COL_LENGTH('dbo.FactInspection','defect_count') IS NULL
 ALTER TABLE dbo.FactInspection ADD defect_count INT NOT NULL CONSTRAINT DF_FactInspection_defect_count DEFAULT 0;
IF COL_LENGTH('dbo.FactInspection','defect_opportunities') IS NULL
 ALTER TABLE dbo.FactInspection ADD defect_opportunities INT NOT NULL CONSTRAINT DF_FactInspection_defect_opportunities DEFAULT 4;
IF COL_LENGTH('dbo.FactInspection','rework_flag') IS NULL
 ALTER TABLE dbo.FactInspection ADD rework_flag BIT NOT NULL CONSTRAINT DF_FactInspection_rework_flag DEFAULT 0;
IF COL_LENGTH('dbo.FactInspection','rework_minutes') IS NULL
 ALTER TABLE dbo.FactInspection ADD rework_minutes DECIMAL(10,2) NOT NULL CONSTRAINT DF_FactInspection_rework_minutes DEFAULT 0;
IF COL_LENGTH('dbo.FactInspection','cycle_time_sec') IS NULL
 ALTER TABLE dbo.FactInspection ADD cycle_time_sec DECIMAL(10,3) NULL;
IF COL_LENGTH('dbo.FactInspection','ideal_cycle_time_sec') IS NULL
 ALTER TABLE dbo.FactInspection ADD ideal_cycle_time_sec DECIMAL(10,3) NULL;
IF COL_LENGTH('dbo.FactInspection','unit_cost_inr') IS NULL
 ALTER TABLE dbo.FactInspection ADD unit_cost_inr DECIMAL(12,2) NULL;
IF COL_LENGTH('dbo.FactInspection','scrap_cost_inr') IS NULL
 ALTER TABLE dbo.FactInspection ADD scrap_cost_inr DECIMAL(12,2) NULL;
IF COL_LENGTH('dbo.FactInspection','rework_cost_inr') IS NULL
ALTER TABLE dbo.FactInspection ADD rework_cost_inr DECIMAL(12,2) NULL;
IF COL_LENGTH('dbo.FactInspection','energy_kwh') IS NULL
 ALTER TABLE dbo.FactInspection ADD energy_kwh DECIMAL(12,5) NULL;
IF COL_LENGTH('dbo.FactInspection','first_pass_flag') IS NULL
 ALTER TABLE dbo.FactInspection ADD first_pass_flag BIT NOT NULL CONSTRAINT DF_FactInspection_first_pass DEFAULT 0;
IF COL_LENGTH('dbo.FactInspection','data_quality_issue_count') IS NULL
 ALTER TABLE dbo.FactInspection ADD data_quality_issue_count INT NOT NULL CONSTRAINT DF_FactInspection_dq_issues DEFAULT 0;
GO

UPDATE dbo.FactInspection
SET defect_count = CASE WHEN ISNULL(defect_type, 'None') = 'None' THEN 0 ELSE 1 END,
		first_pass_flag = 0,
		data_quality_issue_count = 1
WHERE production_order_id IS NULL
	AND data_quality_issue_count = 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_RawInspection_Order' AND object_id=OBJECT_ID('dbo.RawInspection'))
 CREATE INDEX IX_RawInspection_Order ON dbo.RawInspection(production_order_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_RawInspection_Lot' AND object_id=OBJECT_ID('dbo.RawInspection'))
 CREATE INDEX IX_RawInspection_Lot ON dbo.RawInspection(lot_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_FactInspection_Order' AND object_id=OBJECT_ID('dbo.FactInspection'))
 CREATE INDEX IX_FactInspection_Order ON dbo.FactInspection(production_order_id, timestamp);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_FactInspection_Lot' AND object_id=OBJECT_ID('dbo.FactInspection'))
 CREATE INDEX IX_FactInspection_Lot ON dbo.FactInspection(lot_id, timestamp);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_FactInspection_ProductMaterial' AND object_id=OBJECT_ID('dbo.FactInspection'))
 CREATE INDEX IX_FactInspection_ProductMaterial ON dbo.FactInspection(product_family, material_grade, material_thickness_mm);
GO
SELECT TOP (5)
 part_id, production_order_id, lot_id, product_family, material_grade,
 material_thickness_mm, defect_count, scrap_flag, rework_flag,
 cycle_time_sec, unit_cost_inr
FROM dbo.RawInspection
ORDER BY RawID DESC;