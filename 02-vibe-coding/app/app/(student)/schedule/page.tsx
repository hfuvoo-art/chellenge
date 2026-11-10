import Link from "next/link";
import { IconCalendar } from "@/components/icons";
import TopBar from "@/components/TopBar";
import { requireStudent } from "@/lib/auth";
import { weekOf, type ClassRow } from "@/lib/data";
import { roomLabel } from "@/lib/format";
import { addDays, dayNumber, dayShort, humanDate, mondayOf, nowTimeMsk, todayMsk } from "@/lib/time";

export const dynamic = "force-dynamic";

function ClassCell({ c, isToday }: { c: ClassRow; isToday: boolean }) {
  const now = nowTimeMsk();
  const live = isToday && c.status !== "cancelled" && c.start <= now && c.end > now;
  return (
    <div className="cell" style={live ? { background: "var(--brand-soft)", margin: "0 -16px", padding: "12px 16px" } : undefined}>
      <div className="time">{c.start}<div style={{ fontWeight: 500, fontSize: 12 }}>{c.end}</div></div>
      <div className="g">
        <div className={`t1 ${c.status === "cancelled" ? "strike" : ""}`}>{c.subject}</div>
        <div className="t2">
          {c.kind} ·{" "}
          {c.status === "moved" && c.old_room ? <><s>{roomLabel(c.old_room)}</s> → <b style={{ color: "var(--warn)" }}>{roomLabel(c.room)}</b></> : roomLabel(c.room)}
          {c.status === "moved" && c.old_start ? <> · перенос с <s>{c.old_start}</s></> : null}
        </div>
        <div className="t2">{c.teacher}</div>
        {c.status === "cancelled" && c.note && <div className="t2" style={{ color: "var(--bad)" }}>{c.note}</div>}
      </div>
      {live && <span className="badge b-brand">Идёт</span>}
      {c.status === "cancelled" && <span className="badge b-bad">Отменена</span>}
      {c.status === "moved" && <span className="badge b-warn">Изменена</span>}
    </div>
  );
}

export default async function SchedulePage({ searchParams }: { searchParams: Promise<{ d?: string; view?: string }> }) {
  const user = await requireStudent();
  const sp = await searchParams;
  const today = todayMsk();
  const day = sp.d && /^\d{4}-\d{2}-\d{2}$/.test(sp.d) ? sp.d : today;
  const view = sp.view === "week" ? "week" : "day";
  const week = weekOf(user.group_name ?? "", day);
  const mon = mondayOf(day);
  const current = week.find((w) => w.date === day);
  const changes = week.flatMap((w) => w.classes).filter((c) => c.status !== "ok" && c.date >= today);

  return (
    <>
      <TopBar user={user} left={<span className="eyebrow-date">Группа {user.group_name}</span>} />
      <h1 className="large">Расписание</h1>
      <div className="seg glass" role="group" aria-label="Вид">
        <Link href={`/schedule?d=${day}`} aria-current={view === "day" ? "page" : undefined}>День</Link>
        <Link href={`/schedule?d=${day}&view=week`} aria-current={view === "week" ? "page" : undefined}>Неделя</Link>
      </div>

      <div className={view === "day" ? "cols" : "stack"} style={{ marginTop: 6 }}>
        <div className="stack sticky">
          <div className="card" style={{ padding: "6px 8px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 8px 0" }}>
              <Link href={`/schedule?d=${addDays(mon, -7)}&view=${view}`} className="btn ghost sm" aria-label="Прошлая неделя">‹</Link>
              <span className="t2" style={{ fontWeight: 600 }}>{humanDate(mon, false)} – {humanDate(addDays(mon, 6), false)}</span>
              <Link href={`/schedule?d=${addDays(mon, 7)}&view=${view}`} className="btn ghost sm" aria-label="Следующая неделя">›</Link>
            </div>
            <nav className="week" aria-label="Дни недели">
              {week.map((w) => (
                <Link key={w.date} href={`/schedule?d=${w.date}`} aria-current={w.date === day && view === "day" ? "date" : undefined} aria-label={humanDate(w.date)}>
                  {dayShort(w.date)}
                  <b>{dayNumber(w.date)}</b>
                  <i className={w.classes.some((c) => c.status !== "ok") ? "on" : ""} />
                </Link>
              ))}
            </nav>
          </div>
          {changes.length > 0 && view === "day" && (
            <div className="alert" style={{ marginTop: 0 }}>
              <span>Изменений на этой неделе: <b>{changes.length}</b>. Дни с изменениями отмечены точкой.</span>
            </div>
          )}
        </div>

        {view === "day" ? (
          <div className="stack">
            <div className="sh">{humanDate(day)}{day === today ? " · сегодня" : ""}</div>
            {current && current.classes.length > 0 ? (
              <div className="card list">{current.classes.map((c) => <ClassCell key={c.id} c={c} isToday={day === today} />)}</div>
            ) : (
              <div className="card empty">
                <div className="ill"><IconCalendar /></div>
                <div className="t1">Пар нет</div>
                <div className="t2">{day === today ? "Сегодня свободный день" : "В этот день занятий нет"}</div>
              </div>
            )}
          </div>
        ) : (
          <div className="weekgrid">
            {week.map((w) => (
              <section key={w.date}>
                <div className="sh" style={{ paddingTop: 4 }}>{humanDate(w.date)}{w.date === today ? " · сегодня" : ""}</div>
                {w.classes.length ? (
                  <div className="card list" style={{ marginTop: 6 }}>{w.classes.map((c) => <ClassCell key={c.id} c={c} isToday={w.date === today} />)}</div>
                ) : (
                  <div className="card t2" style={{ marginTop: 6 }}>Пар нет</div>
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
