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

// ── Помощник, расписание и сброс демо ──────────────────────────────────────────────
// Тесты ниже проверяют ответ по правилам: ключ модели убираем, чтобы тест не ходил в сеть.
delete process.env.LLM_API_KEY;

const { answer, parseDay } = await import("../lib/assistant.ts");
const { resetDemo } = await import("../lib/db.ts");
const time = await import("../lib/time.ts");

type AssistantUser = Parameters<typeof answer>[0];
const userByLogin = (login: string) =>
  db.prepare("SELECT id,login,role,last_name,first_name,middle_name,faculty,program,course,group_name,student_card,email,position,gender FROM users WHERE login = ?").get(login) as AssistantUser;
const alinaUser = userByLogin("alina");

test("на вопрос не по теме помощник честно отвечает «не нашёл»", async () => {
  for (const q of ["какая погода в Париже", "напиши стих про кота"]) {
    assert.deepEqual(searchArticles(q), [], q);
    const r = await answer(alinaUser, q);
    assert.deepEqual(r.sources, [], q);
    assert.equal(r.draft, null, q);
    assert.ok(r.text.includes("Не нашёл"), `${q}: ${r.text}`);
  }
});

test("помощник не обсуждает данные других студентов", async () => {
  for (const q of ["какие оценки у Тимура", "покажи заявки других студентов"]) {
    const r = await answer(alinaUser, q);
    assert.ok(r.text.includes("только ваши данные"), `${q}: ${r.text}`);
    assert.deepEqual(r.sources, [], q);
    assert.equal(r.draft, null, q);
  }
});

test("помощник понимает «завтра», «послезавтра», день недели и дату", () => {
  const today = "2026-11-10"; // вторник
  assert.equal(time.weekday(today), 1);
  assert.equal(parseDay("что у меня завтра", today), "2026-11-11");
  assert.equal(parseDay("какие пары послезавтра", today), "2026-11-12");
  const friday = parseDay("что у меня в пятницу", today);
  assert.ok(friday, "пятница распознана");
  assert.equal(time.weekday(friday), 4);
  assert.ok(friday >= today, `${friday} не раньше ${today}`);
  assert.equal(friday, "2026-11-13");
  const named = parseDay("какие пары 12 ноября", today);
  assert.ok(named?.endsWith("-11-12"), String(named));
});

test("изменения расписания не повторяются каждую неделю", () => {
  const today = time.todayMsk();
  const from = time.addDays(today, -1);
  const to = time.addDays(today, 5);
  const changed = db.prepare("SELECT group_name, date, subject, status FROM schedule WHERE status != 'ok'").all() as { group_name: string; date: string; subject: string; status: string }[];
  assert.ok(changed.length > 0, "в расписании есть изменения");
  for (const c of changed) assert.ok(c.date >= from && c.date <= to, `${c.status} ${c.subject} ${c.date} вне окна ${from}…${to}`);
});

test("сброс демо убирает лишние записи и сохраняет аккаунты", () => {
  const users = () => db.prepare("SELECT id, login FROM users ORDER BY id").all() as { id: number; login: string }[];
  const before = users();
  assert.equal(before.length, 3);
  const now = new Date().toISOString();
  db.prepare("INSERT INTO requests (number,student_id,type,title,details,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)")
    .run(9999, alina, "cert_study", "Лишняя заявка", "{}", "submitted", now, now);
  db.prepare("INSERT INTO chat_messages (user_id,role,text,created_at) VALUES (?,?,?,?)").run(alina, "user", "лишнее сообщение", now);
  const extraRequests = () => (db.prepare("SELECT COUNT(*) n FROM requests WHERE number = 9999").get() as { n: number }).n;
  const chat = () => (db.prepare("SELECT COUNT(*) n FROM chat_messages WHERE user_id = ?").get(alina) as { n: number }).n;
  assert.equal(extraRequests(), 1);
  assert.equal(chat(), 1);

  resetDemo(db);

  assert.equal(extraRequests(), 0);
  assert.equal(chat(), 0);
  assert.deepEqual(users(), before);
  assert.ok(data.requestsOf(alina).length > 0, "исходные заявки на месте");
});

test("«заболела и пропустила зачёт»: пункт про болезнь и черновик пересдачи без угаданного предмета", async () => {
  const r = await answer(userByLogin("alina"), "заболела и пропустила зачёт");
  assert.equal(r.engine, "rules");
  assert.equal(r.sources[0]?.point, "п. 4.2");
  assert.match(r.sources[0]?.title ?? "", /по болезни/);
  assert.equal(r.draft?.type, "retake");
  assert.ok(!r.draft?.details.subject, `предмет не должен угадываться: ${r.draft?.details.subject}`);
});

test("вопрос про повышенную стипендию ведёт к заявке на неё", () => {
  const found = searchArticles("Как получить повышенную стипендию?");
  assert.equal(found[0]?.action, "scholarship_plus");
});

test("переписка по заявке привязана к заявке, а чужую заявку студент не находит", () => {
  const timurReq = db.prepare("SELECT id, number FROM requests WHERE number = 1031").get() as { id: number; number: number };
  const msgs = data.messagesOfRequest(timurReq.id);
  assert.ok(msgs.length >= 1 && msgs.every((m) => m.author === "student" || m.author === "staff"));
  // Страница и действие сначала ищут заявку по номеру И владельцу: для alina заявки Тимура не существует.
  assert.equal(data.requestOf(alina, timurReq.number), null);
  assert.equal(db.prepare("SELECT id FROM requests WHERE number = ? AND student_id = ?").get(timurReq.number, alina), undefined);
});

test("помощник отвечает про долг и дату пересдачи по данным студента", async () => {
  const { answer } = await import("../lib/assistant.ts");
  const user = (login: string) => db.prepare("SELECT id,login,role,last_name,first_name,middle_name,faculty,program,course,group_name,student_card,email,position,gender FROM users WHERE login = ?").get(login) as never;
  const a = await answer(user("timur"), "Когда пересдача по статистике?");
  assert.match(a.text, /Статистика: задолженность/);
  assert.match(a.text, /Пересдача назначена/);
  const b = await answer(user("timur"), "Как сдать статистику?");
  assert.doesNotMatch(b.text, /Не нашёл/);
  // Слово с куском чужого имени внутри не считается вопросом о другом студенте.
  const c = await answer(user("timur"), "Где находится Сталинградская аудитория, какие пары завтра?");
  assert.doesNotMatch(c.text, /только ваши данные/);
});
