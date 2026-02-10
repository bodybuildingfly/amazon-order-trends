-- Update existing records to use '$' instead of 'USD'
UPDATE tracked_items SET currency = '$' WHERE currency = 'USD';

-- Change the default value for new records
ALTER TABLE tracked_items ALTER COLUMN currency SET DEFAULT '$';
