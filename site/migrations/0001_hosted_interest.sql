CREATE TABLE hosted_interest (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL COLLATE NOCASE UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  consent_version TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('homepage', 'download')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'withdrawn')),
  withdrawn_at TEXT
);
