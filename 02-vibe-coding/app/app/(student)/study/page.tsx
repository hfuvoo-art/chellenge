import Link from "next/link";
import TopBar from "@/components/TopBar";
import { requireStudent } from "@/lib/auth";
import { studySummary } from "@/lib/data";
import { humanDate } from "@/lib/time";

export const dynamic = "force-dynamic";

const CONTROL: Record<string, string> = { exam: "Экзамен", credit: "Зачёт", diff: "Диф. зачёт" };
const TONE_COLOR = { ok: "var(--ok)", warn: "#e08600", bad: "var(--bad)" } as const;

export default async function StudyPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const user = await requireStudent();
  const tab = (await searchParams).tab === "history" ? "history" : "now";
  const sum = studySummary(user.id);
  const avg = sum.avg ?? 0;
  const ring = 2 * Math.PI * 36;

  return (
    <>
      <TopBar user={user} left={<span className="eyebrow-date">{sum.currentSem} семестр</span>} />
      <h1 className="large">Как дела</h1>
      <div className="seg glass" role="group" aria-label="Период">
        <Link href="/study" aria-current={tab === "now" ? "page" : undefined}>Семестр</Link>
        <Link href="/study?tab=history" aria-current={tab === "history" ? "page" : undefined}>Зачётка</Link>
      </div>

      {tab === "now" ? (
        <div className="stack" style={{ marginTop: 6 }}>
          <div className="card" style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <div className="ring" role="img" aria-label={`Средний балл ${avg.toFixed(1)}`}>
              <svg width="88" height="88" aria-hidden>
                <circle cx="44" cy="44" r="36" stroke="#e9ecf2" strokeWidth="10" fill="none" />
                <circle cx="44" cy="44" r="36" stroke={avg >= 4.5 ? "#1a8a47" : avg >= 4 ? "#e08600" : "#c9302c"} strokeWidth="10" fill="none" strokeLinecap="round" strokeDasharray={ring} strokeDashoffset={ring * (1 - Math.min(avg, 5) / 5)} />
              </svg>
              <div className="n">{avg.toFixed(1).replace(".", ",")}</div>
            </div>
            <div>
              <div className="t1">Средний балл</div>
              <div className="t2">По оценкам прошлых сессий</div>
              <span className={`badge ${sum.scholarship ? "b-ok" : "b-bad"}`} style={{ marginTop: 8 }}>
                {sum.scholarship ? "Стипендия сохраняется" : "Стипендия под риском"}
              </span>
            </div>
          </div>

          {(sum.risks.length > 0 || sum.debts.length > 0) && (
            <>
              <div className="sh">Сначала это</div>
              {sum.debts.map((d) => (
                <Link key={d.id} href="/requests/new?type=retake" className="card prio" style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <div className="g"><div className="t1">Долг: {d.name}</div><div className="t2">Задолженность за {d.semester} семестр. Подайте заявление на пересдачу</div></div>
                  <span className="chev" style={{ color: "var(--bad)" }}>›</span>
                </Link>
              ))}
              {sum.risks.map(({ s }) => (
                <Link key={s.id} href={`/study/${s.id}`} className="card prio" style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <div className="g"><div className="t1">{s.name}</div><div className="t2">{s.blocker ?? `${s.points} баллов, для допуска нужно 55`}</div></div>
                  <span className="chev" style={{ color: "var(--bad)" }}>›</span>
                </Link>
              ))}
            </>
          )}

          <div className="sh">Дисциплины · прогноз по баллам</div>
          <div className="card list">
            {sum.forecasts.map(({ s, f }) => (
              <Link key={s.id} href={`/study/${s.id}`} className="cell">
                <span className="dotc" style={{ background: TONE_COLOR[f.tone] }} aria-hidden />
                <div className="g">
                  <div className="t1">{s.name}</div>
                  <div className="t2">{CONTROL[s.control]} · {s.points} из 100{s.exam_date ? ` · ${humanDate(s.exam_date, false)}` : ""}</div>
                  <div className="bar" aria-hidden><i style={{ width: `${s.points}%`, background: TONE_COLOR[f.tone] }} /></div>
                </div>
                {f.tone === "bad" ? <span className="badge b-bad">Риск</span> : <span className="val">{f.label === "Зачёт" ? "зачёт" : f.label}</span>}
              </Link>
            ))}
          </div>
          <p className="t2" style={{ padding: "0 6px" }}>Прогноз: 85+ баллов — «отлично», 70+ — «хорошо», 55+ — «удовлетворительно» или зачёт.</p>
        </div>
      ) : (
        <div className="stack" style={{ marginTop: 6 }}>
          {[...new Set(sum.past.map((s) => s.semester))].map((sem) => (
            <section key={sem}>
              <div className="sh">{sem} семестр</div>
              <div className="card list" style={{ marginTop: 6 }}>
                {sum.past.filter((s) => s.semester === sem).map((s) => (
                  <div className="cell" key={s.id}>
                    <div className="g"><div className="t1">{s.name}</div><div className="t2">{CONTROL[s.control]}</div></div>
                    {s.final === "долг" ? <span className="badge b-bad">Долг</span> : <span className="val">{s.final}</span>}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
