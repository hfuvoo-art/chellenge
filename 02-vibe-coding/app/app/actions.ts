"use server";

import crypto from "node:crypto";
import { revalidatePath } from "next/cache";
import { redirect, RedirectType } from "next/navigation";
import { answer } from "@/lib/assistant";
import { login, logout, requireStaff, requireStudent } from "@/lib/auth";
import { retakeSubjects } from "@/lib/data";
import { getDb, nowIso, resetDemo } from "@/lib/db";
import { roomLabel } from "@/lib/format";
import { requestType, STATUS_LABEL } from "@/lib/request-types";
import { humanDate } from "@/lib/time";

export type FormState = { error?: string; ok?: string; login?: string } | undefined;

export async function loginAction(_: FormState, form: FormData): Promise<FormState> {
  const loginName = String(form.get("login") ?? "");
  const password = String(form.get("password") ?? "");
  // Логин возвращаем обратно в форму, чтобы после ошибки не вводить его заново.
  const keep = loginName.slice(0, 64);
  if (!loginName || !password) return { error: "Введите логин и пароль", login: keep };
  const res = await login(loginName, password);
  if (!res.ok) return { error: res.error, login: keep };
  redirect(res.role === "staff" ? "/staff" : "/");
}

export async function logoutAction(): Promise<void> {
  await logout();
  redirect("/login");
}

// ---------- Студент ----------

/** Проверяет поля заявки по каталогу. Возвращает очищенные значения или текст ошибки. */
function validateDetails(type: string, form: FormData, studentId: number): { details: Record<string, string> } | { error: string } {
  const rt = requestType(type);
  if (!rt) return { error: "Неизвестный тип заявки" };
  const details: Record<string, string> = {};
  const subjects = retakeSubjects(studentId);
  for (const f of rt.fields) {
    const raw = String(form.get(f.name) ?? "").trim().slice(0, 300);
    if (f.kind === "select" && !f.options.includes(raw)) return { error: `Выберите значение в поле «${f.label}»` };
    if (f.kind === "subject" && !subjects.includes(raw)) return { error: "Выберите дисциплину из списка" };
    if (f.kind === "number") {
      const n = Number(raw);
      if (!Number.isInteger(n) || n < f.min || n > f.max) return { error: `В поле «${f.label}» нужно число от ${f.min} до ${f.max}` };
    }
    if ((f.kind === "text" || f.kind === "textarea") && !f.optional && raw.length < 2) return { error: `Заполните поле «${f.label}»` };
    details[f.name] = raw;
  }
  return { details };
}

export async function createRequestAction(_: FormState, form: FormData): Promise<FormState> {
  const user = await requireStudent();
  const type = String(form.get("type") ?? "");
  const v = validateDetails(type, form, user.id);
  if ("error" in v) return { error: v.error };
  const rt = requestType(type)!;
  const db = getDb();
  const now = nowIso();
  // Защита общего демо от спама: не больше 5 заявок от одного студента за час.
  const lastHour = (db.prepare("SELECT COUNT(*) AS n FROM requests WHERE student_id = ? AND created_at > ?").get(user.id, new Date(Date.now() - 3600_000).toISOString()) as { n: number }).n;
  if (lastHour >= 5) return { error: "Слишком много заявок за час. Попробуйте позже." };
  const number = db.transaction(() => {
    const max = (db.prepare("SELECT COALESCE(MAX(number), 1000) AS m FROM requests").get() as { m: number }).m;
    const n = max + 1;
    const id = Number(db.prepare("INSERT INTO requests (number,student_id,type,title,details,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)")
      .run(n, user.id, type, rt.title, JSON.stringify(v.details), "submitted", now, now).lastInsertRowid);
    db.prepare("INSERT INTO request_events (request_id,status,comment,actor,created_at) VALUES (?,?,?,?,?)").run(id, "submitted", null, "Студент", now);
    return n;
  })();
  revalidatePath("/requests");
  // replace: кнопка «Назад» после отправки ведёт в список, а не на заполненную форму (защита от дублей).
  redirect(`/requests/${number}?new=1`, RedirectType.replace);
}

export async function markAllReadAction(): Promise<void> {
  const user = await requireStudent();
  getDb().prepare("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL").run(nowIso(), user.id);
  revalidatePath("/", "layout");
}

export async function askAssistantAction(_: FormState, form: FormData): Promise<FormState> {
  const user = await requireStudent();
  const text = String(form.get("text") ?? "").trim();
  if (!text) return { error: "Напишите вопрос" };
  if (text.length > 500) return { error: "Слишком длинный вопрос, сократите до 500 символов" };
  const db = getDb();
  // Не больше 20 вопросов за 10 минут: защищает сервер и ключ модели.
  const asked = (db.prepare("SELECT COUNT(*) AS n FROM chat_messages WHERE user_id = ? AND role = 'user' AND created_at > ?").get(user.id, new Date(Date.now() - 600_000).toISOString()) as { n: number }).n;
  if (asked >= 20) return { error: "Слишком много вопросов подряд. Подождите пару минут." };
  db.prepare("INSERT INTO chat_messages (user_id,role,text,meta,created_at) VALUES (?,?,?,?,?)").run(user.id, "user", text, null, nowIso());
  const reply = await answer(user, text);
  db.prepare("INSERT INTO chat_messages (user_id,role,text,meta,created_at) VALUES (?,?,?,?,?)").run(
    user.id, "assistant", reply.text, JSON.stringify({ sources: reply.sources, draft: reply.draft, engine: reply.engine }), nowIso(),
  );
  revalidatePath("/assistant");
  return { ok: "sent" };
}

export async function clearChatAction(): Promise<void> {
  const user = await requireStudent();
  getDb().prepare("DELETE FROM chat_messages WHERE user_id = ?").run(user.id);
  revalidatePath("/assistant");
}

// ---------- Сотрудник учебного офиса ----------

function notify(userId: number, kind: string, title: string, body: string, link: string | null) {
  getDb().prepare("INSERT INTO notifications (user_id,kind,title,body,link,created_at) VALUES (?,?,?,?,?,?)").run(userId, kind, title, body, link, nowIso());
}

/** Сообщение по заявке. Студент пишет только в свою заявку (ищем по номеру И владельцу), сотрудник в любую. */
export async function sendRequestMessageAction(_: FormState, form: FormData): Promise<FormState> {
  const text = String(form.get("text") ?? "").trim().slice(0, 500);
  if (text.length < 2) return { error: "Напишите сообщение" };
  const db = getDb();
  const now = nowIso();
  if (form.get("side") === "staff") {
    const staff = await requireStaff();
    const r = db.prepare("SELECT id, number, student_id, title FROM requests WHERE id = ?").get(Number(form.get("id"))) as { id: number; number: number; student_id: number; title: string } | undefined;
    if (!r) return { error: "Заявка не найдена" };
    db.prepare("INSERT INTO request_messages (request_id,author,author_name,text,created_at) VALUES (?,?,?,?,?)").run(r.id, "staff", `${staff.first_name} ${staff.last_name[0]}., учебный офис`, text, now);
    notify(r.student_id, "request", `Ответ учебного офиса по заявке № ${r.number}`, text.length > 120 ? `${text.slice(0, 120)}…` : text, `/requests/${r.number}#chat`);
    revalidatePath("/staff");
    return { ok: "Ответ отправлен. Студент получил уведомление." };
  }
  const user = await requireStudent();
  const r = db.prepare("SELECT id FROM requests WHERE number = ? AND student_id = ?").get(Number(form.get("number")), user.id) as { id: number } | undefined;
  if (!r) return { error: "Заявка не найдена" };
  // Защита от спама: не больше 10 сообщений студента по одной заявке за час.
  const recent = (db.prepare("SELECT COUNT(*) AS n FROM request_messages WHERE request_id = ? AND author = 'student' AND created_at > ?").get(r.id, new Date(Date.now() - 3600_000).toISOString()) as { n: number }).n;
  if (recent >= 10) return { error: "Слишком много сообщений за час. Дождитесь ответа учебного офиса." };
  db.prepare("INSERT INTO request_messages (request_id,author,author_name,text,created_at) VALUES (?,?,?,?,?)").run(r.id, "student", `${user.first_name} ${user.last_name[0]}.`, text, now);
  revalidatePath("/requests");
  return { ok: "Сообщение отправлено. Ответ придёт в уведомления." };
}

const NEXT_STATUS: Record<string, string[]> = {
  submitted: ["in_progress", "rejected"],
  in_progress: ["ready", "rejected"],
  ready: [],
  rejected: [],
};

export async function setRequestStatusAction(_: FormState, form: FormData): Promise<FormState> {
  const staff = await requireStaff();
  const id = Number(form.get("id"));
  const status = String(form.get("status") ?? "");
  const comment = String(form.get("comment") ?? "").trim().slice(0, 500) || null;
  const db = getDb();
  const r = db.prepare("SELECT id, number, student_id, status, title, details FROM requests WHERE id = ?").get(id) as
    | { id: number; number: number; student_id: number; status: string; title: string; details: string } | undefined;
  if (!r) return { error: "Заявка не найдена" };
  if (!NEXT_STATUS[r.status]?.includes(status)) return { error: "Такой переход статуса недоступен" };
  if (status === "rejected" && !comment) return { error: "Напишите студенту причину отказа" };
  const now = nowIso();
  const electronic = String(JSON.parse(r.details).format ?? "").startsWith("Электронная");
  const verify = status === "ready" && electronic ? crypto.randomBytes(6).toString("hex").toUpperCase() : null;
  db.transaction(() => {
    db.prepare("UPDATE requests SET status = ?, staff_comment = COALESCE(?, staff_comment), verify_code = COALESCE(?, verify_code), updated_at = ? WHERE id = ?").run(status, comment, verify, now, r.id);
    db.prepare("INSERT INTO request_events (request_id,status,comment,actor,created_at) VALUES (?,?,?,?,?)").run(r.id, status, comment, `${staff.first_name} ${staff.last_name[0]}., учебный офис`, now);
  })();
  const body = status === "ready" ? (comment ?? "Всё готово.") : status === "rejected" ? `Причина: ${comment}` : "Учебный офис взял заявку в работу.";
  notify(r.student_id, "request", `${r.title}: ${STATUS_LABEL[status].toLowerCase()}`, `Заявка № ${r.number}. ${body}`, `/requests/${r.number}`);
  revalidatePath("/staff");
  return { ok: `Статус: ${STATUS_LABEL[status]}. Студент получил уведомление.` };
}

export async function changeClassAction(_: FormState, form: FormData): Promise<FormState> {
  await requireStaff();
  const id = Number(form.get("id"));
  const action = String(form.get("action") ?? "");
  const room = String(form.get("room") ?? "").trim().slice(0, 40);
  const start = String(form.get("start") ?? "").trim();
  const db = getDb();
  const c = db.prepare("SELECT * FROM schedule WHERE id = ?").get(id) as
    | { id: number; group_name: string; date: string; start: string; end: string; subject: string; room: string; status: string; old_room: string | null; old_start: string | null } | undefined;
  if (!c) return { error: "Пара не найдена" };
  let title = "";
  let body = "";
  if (action === "room") {
    if (room.length < 1) return { error: "Укажите новую аудиторию" };
    db.prepare("UPDATE schedule SET status='moved', old_room = COALESCE(old_room, room), room = ?, note = 'Аудитория изменена' WHERE id = ?").run(room, c.id);
    title = `${c.subject}: новая аудитория`;
    body = `${humanDate(c.date)}, ${c.start}: теперь ${roomLabel(room)} (было: ${roomLabel(c.old_room ?? c.room)}).`;
  } else if (action === "time") {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(start)) return { error: "Время в формате ЧЧ:ММ" };
    const [h, m] = start.split(":").map(Number);
    const endMin = h * 60 + m + 90;
    const end = `${String(Math.floor(endMin / 60) % 24).padStart(2, "0")}:${String(endMin % 60).padStart(2, "0")}`;
    db.prepare("UPDATE schedule SET status='moved', old_start = COALESCE(old_start, start), start = ?, end = ?, note = 'Время изменено' WHERE id = ?").run(start, end, c.id);
    title = `${c.subject}: перенос`;
    body = `${humanDate(c.date)}: пара начнётся в ${start} вместо ${c.old_start ?? c.start}.`;
  } else if (action === "cancel") {
    db.prepare("UPDATE schedule SET status='cancelled', note = 'Пара отменена учебным офисом' WHERE id = ?").run(c.id);
    title = `${c.subject}: пара отменена`;
    body = `${humanDate(c.date)}, ${c.start}. Следите за уведомлениями о переносе.`;
  } else if (action === "restore") {
    db.prepare("UPDATE schedule SET status='ok', room = COALESCE(old_room, room), start = COALESCE(old_start, start), old_room = NULL, old_start = NULL, note = NULL WHERE id = ?").run(c.id);
    title = `${c.subject}: всё по расписанию`;
    body = `${humanDate(c.date)}: изменения отменены, пара проходит как обычно.`;
  } else return { error: "Неизвестное действие" };
  const students = db.prepare("SELECT id FROM users WHERE role='student' AND group_name = ?").all(c.group_name) as { id: number }[];
  for (const s of students) notify(s.id, "schedule", title, body, "/schedule");
  revalidatePath("/staff/schedule");
  return { ok: `Готово. Уведомление получили студенты группы ${c.group_name}: ${students.length}.` };
}

export async function announceAction(_: FormState, form: FormData): Promise<FormState> {
  await requireStaff();
  const title = String(form.get("title") ?? "").trim().slice(0, 120);
  const body = String(form.get("body") ?? "").trim().slice(0, 1000);
  const audience = String(form.get("audience") ?? "all");
  if (title.length < 3 || body.length < 3) return { error: "Заполните заголовок и текст" };
  const db = getDb();
  const groups = (db.prepare("SELECT DISTINCT group_name FROM users WHERE role='student'").all() as { group_name: string }[]).map((g) => g.group_name);
  if (audience !== "all" && !groups.includes(audience)) return { error: "Неизвестная группа" };
  const students = (audience === "all"
    ? db.prepare("SELECT id FROM users WHERE role='student'").all()
    : db.prepare("SELECT id FROM users WHERE role='student' AND group_name = ?").all(audience)) as { id: number }[];
  for (const s of students) notify(s.id, "announcement", title, body, null);
  return { ok: `Объявление отправлено: ${students.length} студентам.` };
}

/** Возвращает демо-данные к исходному состоянию (заявки, расписание, уведомления, чат). Аккаунты и сессии остаются. */
export async function resetDemoAction(): Promise<void> {
  await requireStaff();
  resetDemo();
  revalidatePath("/", "layout");
  redirect("/staff?reset=1");
}
