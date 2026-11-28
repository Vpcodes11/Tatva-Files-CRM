-- Tatva CRM · Files module · database schema (Cloudflare D1 / SQLite)

-- Every business record (site visit, client, booking, payment, plot, expense, ...).
-- One row per record; the record itself is stored as JSON in `data`.
CREATE TABLE IF NOT EXISTS records (
  coll        TEXT NOT NULL,              -- visits, clients, bookings, payments, plots, expenses, landowners,
                                          -- advances, incentives, registry, dastavej, ledger, contractors, plotOwners, meta
  id          TEXT NOT NULL,
  sr          INTEGER,                    -- Sr. number shown in the app
  data        TEXT NOT NULL,              -- JSON
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_by  TEXT,
  PRIMARY KEY (coll, id)
);
CREATE INDEX IF NOT EXISTS records_coll_sr ON records (coll, sr);

-- Every field change made with the pencil (also used for undo).
CREATE TABLE IF NOT EXISTS edits (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  coll       TEXT NOT NULL,
  rec_id     TEXT NOT NULL,
  field      TEXT NOT NULL,
  old        TEXT,                        -- JSON
  new        TEXT,                        -- JSON
  label      TEXT,
  undone     INTEGER NOT NULL DEFAULT 0,
  undo_of    INTEGER,
  user_id    INTEGER,
  user_name  TEXT,
  role       TEXT,
  at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS edits_rec ON edits (coll, rec_id);

-- Holds, bookings, payments, lapses and new visits/expenses, as steps.
CREATE TABLE IF NOT EXISTS steps (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  type       TEXT NOT NULL,
  data       TEXT NOT NULL,               -- JSON
  user_id    INTEGER,
  user_name  TEXT,
  role       TEXT,
  at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name          TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('Agent','Admin','Super admin')),
  pass_hash     TEXT NOT NULL,
  salt          TEXT NOT NULL,
  active        INTEGER NOT NULL DEFAULT 1,
  failed        INTEGER NOT NULL DEFAULT 0,
  locked_until  TEXT,
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  last_login    TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  token       TEXT PRIMARY KEY,
  user_id     INTEGER NOT NULL,
  expires_at  TEXT NOT NULL
);

-- Small key/value settings. `version` goes up on every change so open screens know to refresh.
CREATE TABLE IF NOT EXISTS meta (
  key    TEXT PRIMARY KEY,
  value  TEXT
);
INSERT OR IGNORE INTO meta (key, value) VALUES ('version', '0');

-- Deleted records (Super admin). Every deleted record, and the state before of any record changed by the delete,
-- is kept here so it can be restored from Admin → Deleted items.
CREATE TABLE IF NOT EXISTS trash (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  grp         TEXT NOT NULL,              -- one delete action
  coll        TEXT NOT NULL,
  rec_id      TEXT NOT NULL,
  kind        TEXT NOT NULL,              -- 'deleted' or 'before' (a record that the delete changed)
  data        TEXT NOT NULL,
  label       TEXT,
  user_id     INTEGER,
  user_name   TEXT,
  at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  restored_at TEXT,
  restored_by TEXT
);
CREATE INDEX IF NOT EXISTS trash_grp ON trash (grp);

-- backups (Nov 2026): full copies of `records`, made nightly (cron), by hand, and before a restore
CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, note TEXT, n_records INTEGER, by_name TEXT, at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS backup_records (backup_id INTEGER NOT NULL, coll TEXT NOT NULL, id TEXT NOT NULL, sr INTEGER, data TEXT NOT NULL, PRIMARY KEY (backup_id, coll, id));
