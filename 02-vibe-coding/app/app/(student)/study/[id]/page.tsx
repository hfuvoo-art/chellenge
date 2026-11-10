import Link from "next/link";
import { notFound } from "next/navigation";
import { IconBack } from "@/components/icons";
import { requireStudent } from "@/lib/auth";
import { forecast, subjectOf } from "@/lib/data";
import { humanDate, shortDate } from "@/lib/time";

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
            <div className="t2">{s.blocker ?? `Набрать ещё ${need} балл. до допуска`}</div>
            <div className="row-btns" style={{ marginTop: 10 }}>
              <Link href={`/assistant?q=${encodeURIComponent(`Что делать с предметом «${s.name}»?`)}`} className="btn sm secondary">Спросить помощника</Link>
            </div>
          </div>
        )}
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
