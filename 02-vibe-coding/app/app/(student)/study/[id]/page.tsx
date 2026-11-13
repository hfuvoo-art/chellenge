import Link from "next/link";
import { notFound } from "next/navigation";
import { IconBack } from "@/components/icons";
import { requireStudent } from "@/lib/auth";
import { deadlinesOfSubject, forecast, subjectOf } from "@/lib/data";
import { teacherContact } from "@/lib/format";
import { daysBetween, humanDate, plural, shortDate, todayMsk } from "@/lib/time";

export const dynamic = "force-dynamic";
const CONTROL: Record<string, string> = { exam: "Экзамен", credit: "Зачёт", diff: "Диф. зачёт" };

export default async function SubjectPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireStudent();
  const id = Number((await params).id);
  // Ищем предмет только среди предметов текущего студента.
  const s = Number.isInteger(id) ? subjectOf(user.id, id) : null;
  if (!s) notFound();
  const f = forecast(s);
  const need = Math.max(0, 55 - s.points);
  const contact = teacherContact(s.teacher);
  const today = todayMsk();
  const deadlines = s.final ? [] : deadlinesOfSubject(user.id, s.name);
  const undone = s.works.filter((w) => !w.done);
  return (
    <>
      <div className="topbar"><Link href="/study" className="pillbtn glass"><IconBack /> Учёба</Link></div>
      <h1 className="large" style={{ fontSize: 28 }}>{s.name}</h1>
      <div className="stack">
        <div className="card">
          <div className="kv"><span>Форма контроля</span><span>{CONTROL[s.control]}</span></div>
          <div className="kv"><span>Преподаватель</span><span>{s.teacher}</span></div>
          <div className="kv"><span>Баллы</span><span>{s.points} из 100</span></div>
          <div className="kv"><span>Прогноз</span><span style={{ color: f.tone === "bad" ? "var(--bad)" : undefined }}>{f.label}</span></div>
          {s.exam_date && <div className="kv"><span>Дата</span><span>{humanDate(s.exam_date)}</span></div>}
        </div>
        {(s.blocker || need > 0) && (
          <div className="card prio">
            <div className="t1">Что сделать</div>
            <div className="t2">{s.blocker ?? `Набрать ещё ${need} ${plural(need, "балл", "балла", "баллов")} до допуска`}</div>
            {undone.length > 0 && <div className="t2">Не сдано: {undone.map((w) => w.title).join(", ")}. Работу можно сдать на консультации или прислать преподавателю на почту.</div>}
            <div className="row-btns" style={{ marginTop: 10 }}>
              <a href={`mailto:${contact.email}?subject=${encodeURIComponent(`${s.name}: вопрос по работе`)}`} className="btn sm">Написать преподавателю</a>
              <Link href={`/assistant?q=${encodeURIComponent(`Что делать с предметом «${s.name}»?`)}`} className="btn sm secondary">Спросить помощника</Link>
            </div>
          </div>
        )}
        {deadlines.length > 0 && (
          <>
            <div className="sh">Сроки</div>
            <div className="card list">
              {deadlines.map((d) => {
                const due = todayMsk(new Date(d.due_at));
                const days = daysBetween(today, due);
                return (
                  <div className="cell" key={d.id}>
                    <div className="g"><div className="t1">{d.title}</div><div className="t2">До {humanDate(due, false)}</div></div>
                    <span className={`badge ${days <= 2 ? "b-warn" : "b-gray"}`}>{days < 0 ? "просрочено" : days === 0 ? "сегодня" : days === 1 ? "завтра" : `${days} ${plural(days, "день", "дня", "дней")}`}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}
        <div className="sh">Преподаватель</div>
        <div className="card">
          <div className="kv"><span>Почта</span><span><a className="link" href={`mailto:${contact.email}`}>{contact.email}</a></span></div>
          <div className="kv long"><span>Консультации</span><span>{contact.hours}</span></div>
        </div>
        <div className="sh">Работы</div>
        <div className="card list">
          {s.works.map((w) => (
            <div className="cell" key={w.id}>
              <div className="g"><div className="t1">{w.title}</div><div className="t2">{shortDate(w.date)}</div></div>
              {w.done ? <span className="val">{w.points}/{w.max_points}</span> : <span className="badge b-bad">Не сдана</span>}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
