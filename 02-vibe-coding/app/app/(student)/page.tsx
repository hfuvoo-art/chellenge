import Link from "next/link";
import { IconCalendar, IconChat, IconCheck, IconClock, IconDoc, IconWarn } from "@/components/icons";
import TopBar from "@/components/TopBar";
import { requireStudent } from "@/lib/auth";
import { classesOn, deadlinesOf, nextClass, notificationsOf, requestsOf, studySummary, type ClassRow } from "@/lib/data";
import { STATUS_LABEL } from "@/lib/request-types";
import { addDays, daysBetween, humanDate, minutesBetween, nowTimeMsk, plural, relativeTime, todayMsk } from "@/lib/time";

export const dynamic = "force-dynamic";

function ChangeAlert({ c }: { c: ClassRow }) {
  if (c.status === "moved" && c.old_room)
    return <div className="alert"><IconWarn /><span>Новая аудитория: <s>{c.old_room}</s> → <b>{c.room}</b></span></div>;
  if (c.status === "moved" && c.old_start)
    return <div className="alert"><IconWarn /><span>Перенос: <s>{c.old_start}</s> → <b>{c.start}</b></span></div>;
  return null;
}

export default async function TodayPage() {
  const user = await requireStudent();
  const today = todayMsk();
  const now = nowTimeMsk();
  const group = user.group_name ?? "";
  const classes = classesOn(group, today);
  const nc = nextClass(group);
  const rest = classes.filter((c) => c.id !== nc?.cls.id && c.end > now);
  const summary = studySummary(user.id);
  const deadlines = deadlinesOf(user.id).filter((d) => daysBetween(today, todayMsk(new Date(d.due_at))) <= 7);
  const requests = requestsOf(user.id).filter((r) => r.status !== "rejected" && (r.status !== "ready" || daysBetween(todayMsk(new Date(r.updated_at)), today) <= 3)).slice(0, 3);
  const announcement = notificationsOf(user.id, 20).find((n) => n.kind === "announcement" && !n.read_at);

  let tomorrowFirst: ClassRow | undefined;
  if (!nc) {
    for (let i = 1; i <= 7 && !tomorrowFirst; i++) tomorrowFirst = classesOn(group, addDays(today, i)).find((c) => c.status !== "cancelled");
  }

  return (
    <>
      <TopBar user={user} left={<span className="eyebrow-date">{humanDate(today)}</span>} />
      <h1 className="large">Привет, {user.first_name}</h1>
      <div className="stack">
        {nc ? (
          <Link href="/schedule" className="card hero" aria-label={`Ближайшая пара: ${nc.cls.subject}`}>
            <div className="eyebrow">
              {nc.state === "now" ? `Идёт сейчас · до ${nc.cls.end}` : `Через ${formatIn(minutesBetween(now, nc.cls.start))} · ${nc.cls.start}–${nc.cls.end}`}
            </div>
            <h2 className="h">{nc.cls.subject}</h2>
            <div className="t2">{nc.cls.kind} · ауд. {nc.cls.room} · {nc.cls.teacher}</div>
            <ChangeAlert c={nc.cls} />
          </Link>
        ) : (
          <div className="card">
            <div className="eyebrow">{classes.length ? "Пары на сегодня закончились" : "Сегодня пар нет"}</div>
            {tomorrowFirst ? (
              <>
                <h2 className="h">Дальше: {tomorrowFirst.subject}</h2>
                <div className="t2">{humanDate(tomorrowFirst.date)}, {tomorrowFirst.start} · ауд. {tomorrowFirst.room}</div>
              </>
            ) : (
              <div className="t2">Отдыхайте!</div>
            )}
          </div>
        )}

        {rest.length > 0 && (
          <>
            <div className="sh">Дальше сегодня <Link href="/schedule">Неделя</Link></div>
            <div className="card list">
              {rest.map((c) => (
                <div className="cell" key={c.id}>
                  <span className="time">{c.start}</span>
                  <div className="g">
                    <div className={`t1 ${c.status === "cancelled" ? "strike" : ""}`}>{c.subject}</div>
                    <div className="t2">
                      ауд. {c.status === "moved" && c.old_room ? <><s>{c.old_room}</s> → <b style={{ color: "var(--warn)" }}>{c.room}</b></> : c.room} · {c.kind}
                    </div>
                  </div>
                  {c.status === "cancelled" && <span className="badge b-bad">Отменена</span>}
                  {c.status === "moved" && <span className="badge b-warn">Изменена</span>}
                </div>
              ))}
            </div>
          </>
        )}

        {summary.risks.length > 0 && (
          <Link href={`/study/${summary.risks[0].s.id}`} className="card prio" style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div className="g">
              <div className="t1">Риск: {summary.risks[0].s.name}</div>
              <div className="t2">{summary.risks[0].s.blocker ?? `${summary.risks[0].s.points} баллов из 55 нужных`}</div>
            </div>
            <span className="chev" style={{ color: "var(--bad)" }}>›</span>
          </Link>
        )}

        <div className="sh">Важное</div>
        <div className="card list">
          {requests.map((r) => (
            <Link href={`/requests/${r.number}`} className="cell" key={r.id}>
              <div className="ic" style={{ background: r.status === "ready" ? "var(--ok-soft)" : "var(--brand-soft)", color: r.status === "ready" ? "var(--ok)" : "var(--brand)" }}>
                {r.status === "ready" ? <IconCheck /> : <IconDoc />}
              </div>
              <div className="g">
                <div className="t1">{r.title}</div>
                <div className="t2">№ {r.number} · {STATUS_LABEL[r.status]}{r.status === "ready" && r.verify_code ? " · PDF с QR-кодом" : ""}</div>
              </div>
              <span className={`badge ${r.status === "ready" ? "b-ok" : "b-brand"}`}>{STATUS_LABEL[r.status]}</span>
            </Link>
          ))}
          {deadlines.map((d) => {
            const days = daysBetween(today, todayMsk(new Date(d.due_at)));
            return (
              <Link href="/study" className="cell" key={d.id}>
                <div className="ic" style={{ background: "var(--warn-bg)", color: "var(--warn)" }}><IconClock /></div>
                <div className="g">
                  <div className="t1">{d.title}</div>
                  <div className="t2">До {humanDate(todayMsk(new Date(d.due_at)), false)}, {new Date(d.due_at).toLocaleTimeString("ru-RU", { timeZone: "Europe/Moscow", hour: "2-digit", minute: "2-digit" })}</div>
                </div>
                <span className={`badge ${days <= 2 ? "b-warn" : "b-gray"}`}>{days === 0 ? "сегодня" : days === 1 ? "завтра" : `${days} ${plural(days, "день", "дня", "дней")}`}</span>
              </Link>
            );
          })}
          {announcement && (
            <Link href="/notifications" className="cell">
              <div className="ic" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><IconChat /></div>
              <div className="g">
                <div className="t1">{announcement.title}</div>
                <div className="t2">Объявление · {relativeTime(announcement.created_at)}</div>
              </div>
              <span className="chev">›</span>
            </Link>
          )}
          {requests.length === 0 && deadlines.length === 0 && !announcement && (
            <div className="empty">
              <div className="ill"><IconCalendar /></div>
              <div className="t1">Всё спокойно</div>
              <div className="t2">Нет срочных дедлайнов и новых заявок</div>
            </div>
          )}
        </div>

        <p className="concept">Концепт для конкурса · не официальный сервис · данные вымышленные</p>
      </div>
    </>
  );
}

function formatIn(min: number): string {
  if (min < 60) return `${min} мин`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h} ч ${m} мин` : `${h} ч`;
}
