-- Preserve existing records while allowing the full Unicode Qwen answer.
SET XACT_ABORT ON;
IF EXISTS (
    SELECT 1 FROM sys.columns c
    JOIN sys.types t ON c.user_type_id = t.user_type_id
    WHERE c.object_id = OBJECT_ID('dbo.analysis_records')
      AND c.name = 'qwen_answer'
      AND t.name IN ('text', 'varchar', 'ntext')
)
BEGIN
    ALTER TABLE dbo.analysis_records
        ALTER COLUMN qwen_answer NVARCHAR(MAX) NOT NULL;
END;
