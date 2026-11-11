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

// ── Регрессии помощника: по одному случаю на каждую группу ошибок из прогона живых вопросов ──
const timurUser = userByLogin("timur");
const point = async (u: AssistantUser, q: string) => (await answer(u, q)).sources[0]?.point;

test("помощник отвечает про долги по данным студента, в том числе «долгов нет»", async () => {
  assert.match((await answer(alinaUser, "у меня есть долги?")).text, /задолженностей у вас нет/);
  assert.match((await answer(timurUser, "есть ли у меня хвосты")).text, /Статистика: задолженность/);
  assert.match((await answer(alinaUser, "какой у меня средний балл")).text, /средний балл за прошлые семестры — \d,\d/);
});

test("предмет находится по слову, сокращению и сленгу, но не внутри другого слова", async () => {
  assert.match((await answer(alinaUser, "меня допустят к зачету по международному праву?")).text, /^Международное право: 38 баллов/);
  assert.match((await answer(alinaUser, "сколько баллов по тмо")).text, /^Теория международных отношений/);
  assert.match((await answer(alinaUser, "когда экзамен по английскому")).text, /Английский язык» — 24 декабря/);
  assert.match((await answer(alinaUser, "когда физра")).text, /Ближайшая пара по предмету «Физическая культура»/);
  // «справку» содержит «прав», но это не «Международное право».
  const r = await answer(alinaUser, "сколько делают справку");
  assert.doesNotMatch(r.text, /Международное право/);
  assert.equal(r.sources[0]?.point, "п. 1.3");
  assert.equal(r.draft, null, "на вопрос о сроках черновик не нужен");
});

test("расписание: сокращения дней и «след неделе», без ложных срабатываний", async () => {
  const today = "2026-11-10"; // вторник
  assert.equal(parseDay("пары в чт", today), "2026-11-12");
  assert.equal(parseDay("в пн что", today), "2026-11-16");
  assert.match((await answer(alinaUser, "какая погода завтра")).text, /Не нашёл/);
  assert.equal(await point(timurUser, "прогулял пары что будет"), "п. 4.1");
  assert.equal(await point(alinaUser, "куда идти с заявлением"), "п. 1.1");
  assert.equal(await point(alinaUser, "когда вывесят расписание экзаменов"), "разд. 3");
  const nextMonday = time.addDays(time.mondayOf(time.todayMsk()), 7);
  assert.ok((await answer(alinaUser, "пары на след неделе")).text.startsWith(time.humanDate(nextMonday)));
});

test("приветствия и короткие реплики получают короткий ответ без источников и черновика", async () => {
  for (const q of ["привет", "спасибо", "что ты умеешь", "ок"]) {
    const r = await answer(alinaUser, q);
    assert.doesNotMatch(r.text, /Не нашёл/, q);
    assert.deepEqual(r.sources, [], q);
    assert.equal(r.draft, null, q);
  }
  assert.match((await answer(alinaUser, "привет")).text, /Здравствуйте, Алина/);
});

test("при близких пунктах помощник выбирает нужный", async () => {
  assert.equal(await point(alinaUser, "сколько раз можно пересдавать"), "п. 5.1");
  assert.equal(await point(alinaUser, "до скольки работает деканат"), "п. 1.1");
  assert.equal(await point(alinaUser, "справка для отсрочки от армии"), "п. 1.5");
  assert.equal(await point(alinaUser, "не согласен с оценкой что делать"), "п. 7.1");
  assert.equal(await point(timurUser, "стипендия с долгом"), "п. 2.1");
  const ill = await answer(alinaUser, "я заболела что делать");
  assert.equal(ill.sources[0]?.point, "п. 4.1");
  assert.equal(ill.draft, null, "экзамен не пропущен: заявление на пересдачу не нужно");
});

test("поиск по положениям понимает студенческий сленг", () => {
  assert.equal(searchArticles("когда стипуха")[0]?.id, "scholarship");
  assert.equal(searchArticles("повышка за спорт")[0]?.id, "scholarship-high");
  assert.equal(searchArticles("завалил экзамен как пересдать")[0]?.id, "retake-debt");
  assert.equal(searchArticles("сколько надо на 4")[0]?.id, "grades-scale");
  assert.equal(searchArticles("хочу инд график")[0]?.id, "individual");
  assert.equal(searchArticles("когда экзамены")[0]?.id, "session");
});

test("черновик заявления появляется только по явной просьбе", async () => {
  for (const q of ["электронная справка подойдет?", "пересдача с комиссией это как", "сколько рассматривают заявление на академ"]) {
    assert.equal((await answer(alinaUser, q)).draft, null, q);
  }
  const paper = await answer(alinaUser, "закажи справку об обучении на бумаге");
  assert.equal(paper.draft?.type, "cert_study");
  assert.equal(paper.draft?.details.format, "Бумажная");
  const income = await answer(alinaUser, "справку о доходах дадите");
  assert.match(income.text, /Такой справки в кабинете нет/);
  assert.equal(income.draft, null);
});

test("если заявка уже подана, помощник сообщает о ней и не делает вторую", async () => {
  const retake = await answer(timurUser, "хочу пересдать статистику");
  assert.match(retake.text, /№ 1027/);
  assert.equal(retake.draft, null);
  const ready = await answer(alinaUser, "справка готова?");
  assert.match(ready.text, /Заявка № 1038 «Справка об обучении» — готово/);
  assert.equal(ready.draft, null);
  assert.doesNotMatch((await answer(alinaUser, "где моя заявка")).text, /1027|1031|1041/, "чужие заявки не показываются");
});

test("вопрос о чужих данных без имени тоже получает отказ", async () => {
  for (const q of ["сколько баллов у старосты", "у кого в группе есть долги", "покажи рейтинг группы", "кто в группе отличник", "оценки студентки с 2 курса", "расписание другой группы"]) {
    const r = await answer(alinaUser, q);
    assert.ok(r.text.includes("только ваши данные"), `${q}: ${r.text}`);
    assert.deepEqual(r.sources, [], q);
  }
});

test("дедлайны: по предмету, по работе и до названного дня", async () => {
  assert.match((await answer(timurUser, "когда сдавать проект по эконометрике")).text, /Проект по эконометрике — до/);
  assert.match((await answer(alinaUser, "до какого числа практические")).text, /Практические 2 и 3 по праву — до/);
  assert.match((await answer(alinaUser, "что надо сдать на этой неделе")).text, /^До .* (нужно сдать|сдавать нечего)/);
});

test("грамматика ответов: склонение баллов и не больше одного двоеточия в предложении", async () => {
  assert.match((await answer(timurUser, "что с эконометрикой")).text, /52 балла из 100/);
  assert.match((await answer(timurUser, "деловой английский сколько баллов")).text, /81 балл из 100/);
  const questions = ["как у меня с учебой", "дадут ли мне стипендию", "что с эконометрикой", "какие дедлайны", "расписание на неделю", "мои баллы"];
  for (const u of [alinaUser, timurUser]) for (const q of questions) {
    const { text } = await answer(u, q);
    assert.doesNotMatch(text, /\.\.|::|была (ауд|Актов|Комп|Спорт)/, `${q}: ${text}`);
    for (const sentence of text.split(/(?<=[.!?»])\s+|\n/)) assert.ok((sentence.match(/: /g) ?? []).length < 2, `${q}: ${sentence}`);
  }
});

test("помощник: «что горит на этой неделе» — про сроки, а предмет с днём без пары — честное «пары нет»", async () => {
  const { answer } = await import("../lib/assistant.ts");
  const user = (login: string) => db.prepare("SELECT id,login,role,last_name,first_name,middle_name,faculty,program,course,group_name,student_card,email,position,gender FROM users WHERE login = ?").get(login) as never;
  const a = await answer(user("alina"), "что у меня горит на этой неделе");
  assert.match(a.text, /сдать|срок/i);
  assert.doesNotMatch(a.text, /Понедельник, /);
});

test("помощник: «как пересдать, если болела» тоже даёт черновик пересдачи; отключённые уведомления хранятся по студенту", async () => {
  const { answer } = await import("../lib/assistant.ts");
  const user = (login: string) => db.prepare("SELECT id,login,role,last_name,first_name,middle_name,faculty,program,course,group_name,student_card,email,position,gender FROM users WHERE login = ?").get(login) as never;
  const a = await answer(user("alina"), "как пересдать, если болела");
  assert.equal(a.draft?.type, "retake");
  assert.equal(a.draft?.details.reason, "Болезнь (есть справка)");
  db.prepare("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value").run(`mute:${alina}`, "announcement");
  assert.deepEqual(data.mutedKinds(alina), ["announcement"]);
  assert.deepEqual(data.mutedKinds(timur), []);
  db.prepare("DELETE FROM meta WHERE key = ?").run(`mute:${alina}`);
});
