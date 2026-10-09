-- Apply on each application connection; cache is per connection/database.
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA cache_size = -2048;
PRAGMA mmap_size = 0;
PRAGMA temp_store = FILE;
PRAGMA busy_timeout = 5000;
