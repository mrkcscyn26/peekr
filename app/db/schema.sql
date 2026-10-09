PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS folders (
  id            INTEGER PRIMARY KEY,
  path          TEXT NOT NULL UNIQUE,      -- absolute path
  enabled       INTEGER NOT NULL DEFAULT 1,
  last_scan_at  TEXT,                      -- UTC ISO 8601
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS excluded_paths (
  id         INTEGER PRIMARY KEY,
  folder_id  INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
  path       TEXT NOT NULL,
  UNIQUE (folder_id, path)
);

CREATE TABLE IF NOT EXISTS files (
  id            INTEGER PRIMARY KEY,
  folder_id     INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
  current_path  TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  extension     TEXT NOT NULL,             -- lowercase with dot, e.g. .pdf
  size_bytes    INTEGER NOT NULL,
  created_at    TEXT,                      -- file system times
  modified_at   TEXT NOT NULL,
  content_hash  TEXT,                      -- SHA-256 hex of the file bytes
  category      TEXT,
  status        TEXT NOT NULL,             -- pending | indexed | skipped | error | deleted
  status_reason TEXT,                      -- reason code, see Section 8.11
  indexed_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_hash   ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_id, status);

CREATE TABLE IF NOT EXISTS chunks (
  id          INTEGER PRIMARY KEY,
  file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  location    TEXT,                        -- 'page 3', 'slide 5', 'part 2'
  text        TEXT NOT NULL,
  embedding   BLOB NOT NULL,               -- float32, L2-normalized
  UNIQUE (file_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text, content='chunks', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TABLE IF NOT EXISTS summaries (
  file_id       INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
  content_hash  TEXT NOT NULL,             -- hash the summary was made from
  summary_text  TEXT NOT NULL,
  model_name    TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY,
  file_id      INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  event_type   TEXT NOT NULL,              -- baseline | created | modified | moved | renamed | deleted
  old_path     TEXT,
  new_path     TEXT,
  hash_before  TEXT,
  hash_after   TEXT,
  occurred_at  TEXT NOT NULL,              -- detection time, UTC
  source       TEXT NOT NULL               -- scan | watcher | reconcile
);
CREATE INDEX IF NOT EXISTS idx_events_file ON events(file_id, occurred_at);

CREATE TABLE IF NOT EXISTS categories (
  name        TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  embedding   BLOB                         -- float32, normalized
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL                      -- e.g. embedding_model, embedding_dim, schema_version
);
