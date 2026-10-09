USE QualityAnalytics;
GO
INSERT INTO dbo.DimShift (Shift, ShiftOrder, StartTime, EndTime)
SELECT seed.Shift, seed.ShiftOrder, seed.StartTime, seed.EndTime
FROM (VALUES
	('Shift A', 1, CAST('06:00' AS TIME), CAST('14:00' AS TIME)),
	('Shift B', 2, CAST('14:00' AS TIME), CAST('22:00' AS TIME)),
	('Shift C', 3, CAST('22:00' AS TIME), CAST('06:00' AS TIME))
) AS seed(Shift, ShiftOrder, StartTime, EndTime)
WHERE NOT EXISTS (
	SELECT 1 FROM dbo.DimShift AS existing WHERE existing.Shift = seed.Shift
);

INSERT INTO dbo.DimMachine (MachineID, MachineName)
SELECT seed.MachineID, seed.MachineName
FROM (VALUES
	('Laser-01', 'Laser-01'),
	('Laser-02', 'Laser-02'),
	('Laser-03', 'Laser-03'),
	('Laser-04', 'Laser-04')
) AS seed(MachineID, MachineName)
WHERE NOT EXISTS (
	SELECT 1 FROM dbo.DimMachine AS existing WHERE existing.MachineID = seed.MachineID
);

INSERT INTO dbo.DimSupplier (Supplier)
SELECT seed.Supplier
FROM (VALUES ('SteelCo'), ('MetalWorks'), ('AlloyPlus')) AS seed(Supplier)
WHERE NOT EXISTS (
	SELECT 1 FROM dbo.DimSupplier AS existing WHERE existing.Supplier = seed.Supplier
);

INSERT INTO dbo.DimDefectType (DefectType, DefectRank)
SELECT seed.DefectType, seed.DefectRank
FROM (VALUES
	('Edge Crack', 1),
	('Dim. Out of Tol.', 2),
	('Dross', 3),
	('Burr', 4),
	('Warping', 5),
	('None', 6)
) AS seed(DefectType, DefectRank)
WHERE NOT EXISTS (
	SELECT 1 FROM dbo.DimDefectType AS existing WHERE existing.DefectType = seed.DefectType
);