// Все даты считаем по Москве, независимо от часового пояса сервера.
const TZ = "Europe/Moscow";

export function todayMsk(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export function nowTimeMsk(now = new Date()): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false }).format(now);
}

export function addDays(date: string, days: number): string {
  const d = new Date(date + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** 0 = понедельник ... 6 = воскресенье */
export function weekday(date: string): number {
  const d = new Date(date + "T12:00:00Z");
  return (d.getUTCDay() + 6) % 7;
}

export function mondayOf(date: string): string {
  return addDays(date, -weekday(date));
}

const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
const DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
const DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export function humanDate(date: string, withDay = true): string {
  const [, m, d] = date.split("-").map(Number);
  const base = `${d} ${MONTHS[m - 1]}`;
  return withDay ? `${DAYS[weekday(date)]}, ${base}` : base;
}

export function shortDate(date: string): string {
  const [, m, d] = date.split("-").map(Number);
  return `${d} ${MONTHS_SHORT[m - 1]}`;
}

export function dayShort(date: string): string {
  return DAYS_SHORT[weekday(date)];
}

export function dayNumber(date: string): number {
  return Number(date.slice(8, 10));
}

export function minutesBetween(fromHHMM: string, toHHMM: string): number {
  const [h1, m1] = fromHHMM.split(":").map(Number);
  const [h2, m2] = toHHMM.split(":").map(Number);
  return h2 * 60 + m2 - (h1 * 60 + m1);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((new Date(to + "T12:00:00Z").getTime() - new Date(from + "T12:00:00Z").getTime()) / 86400000);
}

export function relativeTime(iso: string, now = new Date()): string {
  const diff = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60000));
  if (diff < 1) return "только что";
  if (diff < 60) return `${diff} мин назад`;
  const h = Math.round(diff / 60);
  if (h < 24) return `${h} ч назад`;
  const d = Math.round(h / 24);
  if (d === 1) return "вчера";
  if (d < 7) return `${d} дн. назад`;
  return shortDate(todayMsk(new Date(iso)));
}

export function plural(n: number, one: string, few: string, many: string): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b === 1) return one;
  return many;
}

/** Срок приёма заявлений на повышенную стипендию в демо: считается от сегодняшнего дня, чтобы не устаревал. */
export function scholarshipDeadline(): string {
  return addDays(todayMsk(new Date(Date.now() - 4 * 3600_000)), 9);
}
