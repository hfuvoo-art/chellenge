import "server-only";
import bcrypt from "bcryptjs";
import crypto from "node:crypto";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { getDb } from "./db";

// Вход: пароль сверяется с bcrypt-хэшем. После входа выдаём случайный токен в httpOnly-cookie,
// в базе храним только его SHA-256. Каждый запрос к данным берёт пользователя из сессии, а не из адреса.

export const SESSION_COOKIE = "dk_session";
const SESSION_DAYS = 7;

export type User = {
  id: number;
  login: string;
  role: "student" | "staff";
  last_name: string;
  first_name: string;
  middle_name: string;
  faculty: string;
  program: string;
  course: number | null;
  group_name: string | null;
  student_card: string | null;
  email: string | null;
  position: string | null;
  gender: "f" | "m" | null;
};

const USER_COLUMNS = "u.id,u.login,u.role,u.last_name,u.first_name,u.middle_name,u.faculty,u.program,u.course,u.group_name,u.student_card,u.email,u.position,u.gender";

const sha256 = (s: string) => crypto.createHash("sha256").update(s).digest("hex");

// Ограничение попыток входа на пару «IP + логин»: после 5 неудач за 10 минут следующая попытка
// разрешается раз в минуту. Подбор пароля это тормозит, а человека, который ошибся (или чей
// тестовый аккаунт «заняли» с того же адреса), не запирает надолго. Чужие IP на блокировку не влияют.
const attempts = new Map<string, { n: number; windowEnd: number; lockedUntil: number }>();
const WINDOW_MS = 10 * 60 * 1000;
const LOCK_MS = 60 * 1000;

export function tooManyAttempts(key: string): boolean {
  const a = attempts.get(key);
  return !!a && a.lockedUntil > Date.now();
}
function failAttempt(key: string) {
  const now = Date.now();
  let a = attempts.get(key);
  if (!a || a.windowEnd < now) { a = { n: 0, windowEnd: now + WINDOW_MS, lockedUntil: 0 }; attempts.set(key, a); }
  a.n++;
  if (a.n >= 5) a.lockedUntil = now + LOCK_MS;
}

// Хэш-«пустышка», чтобы время ответа не выдавало, существует ли логин.
const DUMMY_HASH = bcrypt.hashSync("dummy-password-for-timing", 10);

export async function login(loginRaw: string, password: string): Promise<{ ok: true; role: User["role"] } | { ok: false; error: string }> {
  const loginName = loginRaw.trim().toLowerCase();
  const ip = (await headers()).get("x-forwarded-for")?.split(",")[0]?.trim() || "local";
  const key = `${ip}|${loginName}`;
  if (tooManyAttempts(key)) return { ok: false, error: "Слишком много неверных попыток. Подождите минуту и попробуйте снова." };

  const db = getDb();
  const row = db.prepare("SELECT id, role, password_hash FROM users WHERE login = ?").get(loginName) as
    | { id: number; role: User["role"]; password_hash: string }
    | undefined;
  const valid = bcrypt.compareSync(password, row?.password_hash ?? DUMMY_HASH);
  if (!row || !valid) {
    failAttempt(key);
    return { ok: false, error: "Неверный логин или пароль" };
  }
  attempts.delete(key);

  const token = crypto.randomBytes(32).toString("base64url");
  const now = Date.now();
  db.prepare("DELETE FROM sessions WHERE expires_at < ?").run(now);
  db.prepare("INSERT INTO sessions (token_hash,user_id,created_at,expires_at) VALUES (?,?,?,?)").run(sha256(token), row.id, now, now + SESSION_DAYS * 86400000);
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production" && process.env.INSECURE_COOKIES !== "1",
    path: "/",
    maxAge: SESSION_DAYS * 86400,
  });
  return { ok: true, role: row.role };
}

export async function logout(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (token) getDb().prepare("DELETE FROM sessions WHERE token_hash = ?").run(sha256(token));
  jar.delete(SESSION_COOKIE);
}

export async function currentUser(): Promise<User | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  const row = getDb()
    .prepare(`SELECT ${USER_COLUMNS} FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?`)
    .get(sha256(token), Date.now()) as User | undefined;
  return row ?? null;
}

export async function requireStudent(): Promise<User> {
  const u = await currentUser();
  if (!u) redirect("/login");
  if (u.role !== "student") redirect("/staff");
  return u;
}

export async function requireStaff(): Promise<User> {
  const u = await currentUser();
  if (!u) redirect("/login");
  if (u.role !== "staff") redirect("/");
  return u;
}
