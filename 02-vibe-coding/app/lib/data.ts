import "server-only";
import { getDb } from "./db";
import { addDays, mondayOf, nowTimeMsk, todayMsk } from "./time";

// Все функции берут id студента из сессии (его передаёт страница после requireStudent).
// Ни одна функция не принимает id из адреса без проверки владельца.

export type ClassRow = {
  id: number; group_name: string; date: string; start: string; end: string; subject: string; kind: string;
  room: string; teacher: string; status: "ok" | "moved" | "cancelled"; old_room: string | null; old_start: string | null; note: string | null;
};

export function classesOn(group: string, date: string): ClassRow[] {
  return getDb().prepare("SELECT * FROM schedule WHERE group_name = ? AND date = ? ORDER BY start").all(group, date) as ClassRow[];
}

export function classesBetween(group: string, from: string, to: string): ClassRow[] {
  return getDb().prepare("SELECT * FROM schedule WHERE group_name = ? AND date >= ? AND date <= ? ORDER BY date, start").all(group, from, to) as ClassRow[];
}

export function weekOf(group: string, date: string) {
  const mon = mondayOf(date);
  const days = Array.from({ length: 6 }, (_, i) => addDays(mon, i));
  const rows = classesBetween(group, days[0], days[5]);
  return days.map((d) => ({ date: d, classes: rows.filter((r) => r.date === d) }));
}

/** Ближайшая пара сегодня (идущая или следующая), без отменённых. */
export function nextClass(group: string) {
  const today = todayMsk();
  const t = nowTimeMsk();
  const list = classesOn(group, today).filter((c) => c.status !== "cancelled");
  const current = list.find((c) => c.start <= t && c.end > t);
  if (current) return { cls: current, state: "now" as const };
  const next = list.find((c) => c.start > t);
  if (next) return { cls: next, state: "next" as const };
  return null;
}

export type Subject = {
  id: number; semester: number; name: string; control: "exam" | "credit" | "diff"; teacher: string;
  points: number; final: string | null; blocker: string | null; exam_date: string | null;
};
export type Work = { id: number; subject_id: number; date: string; title: string; points: number | null; max_points: number; done: number };

export function subjectsOf(studentId: number): Subject[] {
  return getDb().prepare("SELECT id,semester,name,control,teacher,points,final,blocker,exam_date FROM subjects WHERE student_id = ? ORDER BY semester DESC, id").all(studentId) as Subject[];
}

export function subjectOf(studentId: number, subjectId: number): (Subject & { works: Work[] }) | null {
  const db = getDb();
  const s = db.prepare("SELECT id,semester,name,control,teacher,points,final,blocker,exam_date FROM subjects WHERE id = ? AND student_id = ?").get(subjectId, studentId) as Subject | undefined;
  if (!s) return null;
  const works = db.prepare("SELECT * FROM works WHERE subject_id = ? ORDER BY date").all(s.id) as Work[];
  return { ...s, works };
}

/** Прогноз оценки по баллам: 85+ = 5, 70+ = 4, 55+ = 3, ниже = риск. */
export function forecast(s: Subject): { label: string; tone: "ok" | "warn" | "bad"; mark: number | null } {
  if (s.blocker || s.points < 55) return { label: s.control === "credit" ? "Риск незачёта" : "Риск недопуска", tone: "bad", mark: null };
  if (s.control === "credit") return { label: "Зачёт", tone: "ok", mark: null };
  if (s.points >= 85) return { label: "5", tone: "ok", mark: 5 };
  if (s.points >= 70) return { label: "4", tone: "warn", mark: 4 };
  return { label: "3", tone: "warn", mark: 3 };
}

export function studySummary(studentId: number) {
  const all = subjectsOf(studentId);
  const currentSem = Math.max(...all.map((s) => s.semester));
  const current = all.filter((s) => s.semester === currentSem);
  const past = all.filter((s) => s.semester !== currentSem);
  const pastMarks = past.map((s) => Number(s.final)).filter((n) => !Number.isNaN(n) && n > 0);
  const debts = past.filter((s) => s.final === "долг");
  const avg = pastMarks.length ? pastMarks.reduce((a, b) => a + b, 0) / pastMarks.length : null;
  const forecasts = current.map((s) => ({ s, f: forecast(s) }));
  const risks = forecasts.filter((x) => x.f.tone === "bad");
  const examMarks = forecasts.filter((x) => x.f.mark !== null).map((x) => x.f.mark as number);
  const minExam = examMarks.length ? Math.min(...examMarks) : 5;
  const scholarship = risks.length === 0 && debts.length === 0 && minExam >= 4;
  return { currentSem, current, past, avg, debts, risks, forecasts, scholarship };
}

export type Deadline = { id: number; title: string; subject: string | null; due_at: string };
export function deadlinesOf(studentId: number): Deadline[] {
  return getDb().prepare("SELECT id,title,subject,due_at FROM deadlines WHERE student_id = ? AND due_at >= ? ORDER BY due_at").all(studentId, new Date(Date.now() - 3600_000).toISOString()) as Deadline[];
}

export type RequestRow = {
  id: number; number: number; student_id: number; type: string; title: string; details: string;
  status: "submitted" | "in_progress" | "ready" | "rejected"; staff_comment: string | null; verify_code: string | null; created_at: string; updated_at: string;
};
export type RequestEvent = { id: number; status: string; comment: string | null; actor: string; created_at: string };

export function requestsOf(studentId: number): RequestRow[] {
  return getDb().prepare("SELECT * FROM requests WHERE student_id = ? ORDER BY created_at DESC").all(studentId) as RequestRow[];
}

/** Заявку видит только её владелец. Чужой номер в адресе даёт «не найдено». */
export function requestOf(studentId: number, number: number): (RequestRow & { events: RequestEvent[] }) | null {
  const db = getDb();
  const r = db.prepare("SELECT * FROM requests WHERE number = ? AND student_id = ?").get(number, studentId) as RequestRow | undefined;
  if (!r) return null;
  const events = db.prepare("SELECT id,status,comment,actor,created_at FROM request_events WHERE request_id = ? ORDER BY created_at, id").all(r.id) as RequestEvent[];
  return { ...r, events };
}

export type Notification = { id: number; kind: string; title: string; body: string; link: string | null; created_at: string; read_at: string | null };
export function notificationsOf(userId: number, limit = 50): Notification[] {
  return getDb().prepare("SELECT id,kind,title,body,link,created_at,read_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?").all(userId, limit) as Notification[];
}
export function unreadCount(userId: number): number {
  return (getDb().prepare("SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND read_at IS NULL").get(userId) as { n: number }).n;
}
