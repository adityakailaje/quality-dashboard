USE QualityAnalytics;
GO
DECLARE @RequiredColumns TABLE (TableName SYSNAME NOT NULL, ColumnName SYSNAME NOT NULL);
INSERT INTO @RequiredColumns (TableName, ColumnName)
VALUES
	('RawInspection', 'production_order_id'),
	('RawInspection', 'lot_id'),
	('RawInspection', 'product_family'),
	('RawInspection', 'material_grade'),
	('RawInspection', 'material_thickness_mm'),
	('RawInspection', 'operator_id'),
	('RawInspection', 'defect_count'),
	('RawInspection', 'defect_opportunities'),
	('RawInspection', 'rework_flag'),
	('RawInspection', 'rework_minutes'),
	('RawInspection', 'cycle_time_sec'),
	('RawInspection', 'ideal_cycle_time_sec'),
	('RawInspection', 'unit_cost_inr'),
	('RawInspection', 'scrap_cost_inr'),
	('RawInspection', 'rework_cost_inr'),
	('RawInspection', 'energy_kwh'),
	('FactInspection', 'production_order_id'),
	('FactInspection', 'lot_id'),
	('FactInspection', 'product_family'),
	('FactInspection', 'material_grade'),
	('FactInspection', 'material_thickness_mm'),
	('FactInspection', 'operator_id'),
	('FactInspection', 'defect_count'),
	('FactInspection', 'defect_opportunities'),
	('FactInspection', 'rework_flag'),
	('FactInspection', 'rework_minutes'),
	('FactInspection', 'cycle_time_sec'),
	('FactInspection', 'ideal_cycle_time_sec'),
	('FactInspection', 'unit_cost_inr'),
	('FactInspection', 'scrap_cost_inr'),
	('FactInspection', 'rework_cost_inr'),
	('FactInspection', 'energy_kwh'),
	('FactInspection', 'first_pass_flag'),
	('FactInspection', 'data_quality_issue_count');

IF EXISTS (
	SELECT 1
	FROM @RequiredColumns AS required
	WHERE COL_LENGTH('dbo.' + required.TableName, required.ColumnName) IS NULL
)
BEGIN
	;THROW 51000, 'Required v2 columns are missing; run 06_v2_modifications.sql first.', 1;
END;

SELECT COUNT(*) AS RawRows,
	   SUM(CASE WHEN processed = 0 THEN 1 ELSE 0 END) AS WaitingForETL,
	   SUM(CASE WHEN production_order_id IS NULL OR lot_id IS NULL
				  OR defect_count IS NULL OR cycle_time_sec IS NULL
				THEN 1 ELSE 0 END) AS RawRowsMissingV2Fields
FROM dbo.RawInspection;

SELECT COUNT(*) AS FactRows,
	   SUM(CASE WHEN first_pass_flag = 1 THEN 1 ELSE 0 END) AS FirstPassRows,
	   SUM(CASE WHEN data_quality_issue_count > 0 THEN 1 ELSE 0 END) AS RowsWithDataQualityIssues,
	   SUM(CASE WHEN production_order_id IS NULL OR lot_id IS NULL
				  OR defect_count IS NULL OR cycle_time_sec IS NULL
				THEN 1 ELSE 0 END) AS FactRowsMissingV2Fields
FROM dbo.FactInspection;

SELECT TOP (20) *
FROM dbo.RawInspection
ORDER BY RawID DESC;