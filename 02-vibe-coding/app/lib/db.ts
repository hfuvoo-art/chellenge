import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";
import { seed } from "./seed";

// Одна база SQLite на диске сервера. Путь задаётся переменной DATABASE_PATH.
// Для роста нагрузки схему можно перенести в PostgreSQL без смены логики: все запросы лежат в lib/.

const SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  login TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('student','staff')),
  last_name TEXT NOT NULL,
  first_name TEXT NOT NULL,
  middle_name TEXT NOT NULL DEFAULT '',
  faculty TEXT NOT NULL DEFAULT '',
  program TEXT NOT NULL DEFAULT '',
  course INTEGER,
  group_name TEXT,
  student_card TEXT,
  email TEXT,
  position TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS schedule (
  id INTEGER PRIMARY KEY,
  group_name TEXT NOT NULL,
  date TEXT NOT NULL,
  start TEXT NOT NULL,
  end TEXT NOT NULL,
  subject TEXT NOT NULL,
  kind TEXT NOT NULL,
  room TEXT NOT NULL,
  teacher TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','moved','cancelled')),
  old_room TEXT,
  old_start TEXT,
  note TEXT
);
CREATE INDEX IF NOT EXISTS schedule_group_date ON schedule(group_name, date);
CREATE TABLE IF NOT EXISTS subjects (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  semester INTEGER NOT NULL,
  name TEXT NOT NULL,
  control TEXT NOT NULL CHECK (control IN ('exam','credit','diff')),
  teacher TEXT NOT NULL,
  points INTEGER NOT NULL,
  final TEXT,
  blocker TEXT,
  exam_date TEXT
);
CREATE TABLE IF NOT EXISTS works (
  id INTEGER PRIMARY KEY,
  subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  title TEXT NOT NULL,
  points INTEGER,
  max_points INTEGER NOT NULL,
  done INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS deadlines (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  subject TEXT,
  due_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY,
  number INTEGER NOT NULL UNIQUE,
  student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  details TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('submitted','in_progress','ready','rejected')),
  staff_comment TEXT,
  verify_code TEXT UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS request_events (
  id INTEGER PRIMARY KEY,
  request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  comment TEXT,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  link TEXT,
  created_at TEXT NOT NULL,
  read_at TEXT
);
CREATE INDEX IF NOT EXISTS notifications_user ON notifications(user_id, created_at);
CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user','assistant')),
  text TEXT NOT NULL,
  meta TEXT,
  created_at TEXT NOT NULL
);
`;

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (db) return db;
  const file = process.env.DATABASE_PATH || path.join(process.cwd(), "data", "dekanat.db");
  fs.mkdirSync(path.dirname(file), { recursive: true });
  db = new Database(file);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  db.exec(SCHEMA);
  const count = db.prepare("SELECT COUNT(*) AS n FROM users").get() as { n: number };
  if (count.n === 0) {
    // Пустая база: заполняем вымышленными данными при первом запуске.
    seed(db);
  }
  return db;
}

export function nowIso(): string {
  return new Date().toISOString();
}
