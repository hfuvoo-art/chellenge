// Проверки доступа к данным на уровне сервера: npm test
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

process.env.DATABASE_PATH = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "dk-")), "test.db");

const { getDb } = await import("../lib/db.ts");
const data = await import("../lib/data.ts");
const { searchArticles } = await import("../lib/regulations.ts");

const db = getDb();
const id = (login: string) => (db.prepare("SELECT id FROM users WHERE login = ?").get(login) as { id: number }).id;
const alina = id("alina");
const timur = id("timur");

test("пароли хранятся только как bcrypt-хэш", () => {
  const rows = db.prepare("SELECT password_hash FROM users").all() as { password_hash: string }[];
  for (const r of rows) {
    assert.match(r.password_hash, /^\$2[aby]\$10\$/);
    assert.ok(!r.password_hash.includes("demo2026"));
  }
});

test("студент не открывает чужую заявку по номеру", () => {
  const timurRequest = db.prepare("SELECT number FROM requests WHERE student_id = ? LIMIT 1").get(timur) as { number: number };
  assert.equal(data.requestOf(alina, timurRequest.number), null);
  assert.ok(data.requestOf(timur, timurRequest.number));
});

test("студент не открывает чужой предмет по id", () => {
  const timurSubject = db.prepare("SELECT id FROM subjects WHERE student_id = ? LIMIT 1").get(timur) as { id: number };
  assert.equal(data.subjectOf(alina, timurSubject.id), null);
});

test("списки заявок и уведомлений содержат только свои записи", () => {
  assert.ok(data.requestsOf(alina).every((r) => r.student_id === alina));
  const own = data.notificationsOf(alina).map((n) => n.id);
  const ids = (db.prepare("SELECT id FROM notifications WHERE user_id = ?").all(alina) as { id: number }[]).map((x) => x.id);
  assert.deepEqual(own.sort(), ids.sort());
});

test("минимум два студента с разными данными и сотрудник", () => {
  const students = db.prepare("SELECT group_name, faculty FROM users WHERE role='student'").all() as { group_name: string; faculty: string }[];
  assert.ok(students.length >= 2);
  assert.notEqual(students[0].group_name, students[1].group_name);
  assert.equal((db.prepare("SELECT COUNT(*) n FROM users WHERE role='staff'").get() as { n: number }).n, 1);
});

test("на сегодня в расписании есть пары и изменения", () => {
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Europe/Moscow" });
  const isSunday = new Date(today + "T12:00:00Z").getUTCDay() === 0;
  const list = data.classesOn("МО-2-04", today);
  if (!isSunday) assert.ok(list.some((c) => c.status === "moved"), "сегодня у демо-группы есть смена аудитории");
});

test("помощник находит пункт положения про пропуск по болезни", () => {
  const found = searchArticles("заболела и пропустила зачёт");
  assert.equal(found[0]?.id, "retake-illness");
});
