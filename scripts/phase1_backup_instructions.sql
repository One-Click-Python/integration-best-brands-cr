-- ================================================
-- FASE 1: BACKUP DE BASE DE DATOS RMS
-- ================================================
-- CRITICAL: Execute this BEFORE any order polling tests
-- ================================================

-- Option 1: Full Database Backup (RECOMMENDED)
BACKUP DATABASE [RMS_Database]
TO DISK = 'C:\Backups\RMS_Database_OrderPollingTest_20250112.bak'
WITH FORMAT,
     MEDIANAME = 'RMS_OrderPollingTest',
     NAME = 'Full Backup Before Order Polling Tests',
     COMPRESSION,
     STATS = 10;
GO

-- Option 2: Backup Only Order Tables (Faster, but limited)
-- Note: This doesn't support full restore, only for reference
SELECT * INTO [Order_Backup_20250112]
FROM [Order]
WHERE ChannelType = 2;

SELECT * INTO [OrderEntry_Backup_20250112]
FROM [OrderEntry]
WHERE OrderID IN (SELECT ID FROM [Order] WHERE ChannelType = 2);

-- Verify Backup
SELECT
    database_name,
    backup_start_date,
    backup_finish_date,
    backup_size / 1024.0 / 1024.0 AS backup_size_mb,
    compressed_backup_size / 1024.0 / 1024.0 AS compressed_size_mb
FROM msdb.dbo.backupset
WHERE database_name = 'RMS_Database'
ORDER BY backup_start_date DESC;
GO

-- ================================================
-- INSTRUCTIONS:
-- ================================================
-- 1. Open SQL Server Management Studio (SSMS)
-- 2. Connect to your RMS SQL Server instance
-- 3. Execute the "Option 1" script above (RECOMMENDED)
-- 4. Verify the backup file exists at the specified path
-- 5. Record the backup location and timestamp
-- 6. Proceed to baseline documentation (scripts/phase1_validation.py)
-- ================================================
