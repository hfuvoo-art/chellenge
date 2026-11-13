import { clearChatAction } from "@/app/actions";
import Composer, { Suggestion } from "@/components/Composer";
import { IconSpark } from "@/components/icons";
import RequestForm from "@/components/RequestForm";
import { requireStudent } from "@/lib/auth";
import type { Reply } from "@/lib/assistant";
import { retakeSubjects, studySummary } from "@/lib/data";
import { getDb } from "@/lib/db";
import { articleBy } from "@/lib/regulations";
import { requestType } from "@/lib/request-types";

export const dynamic = "force-dynamic";

type Msg = { id: number; role: "user" | "assistant"; text: string; meta: string | null; created_at: string };

// Подсказки зависят от студента: формулировка по полу, справка в военкомат только там, где она уместна.
function suggestions(gender: "f" | "m" | null, hasDebt: boolean): string[] {
  return [
    gender === "m" ? "Заболел и пропустил зачёт. Что делать?" : gender === "f" ? "Заболела и пропустила зачёт. Что делать?" : "Пропуск зачёта по болезни. Что делать?",
    hasDebt ? "Как закрыть долг?" : "Как у меня дела с учёбой?",
    gender === "m" ? "Нужна справка для военкомата" : "Нужна справка об обучении",
    "Какие пары завтра?",
    "Как получить повышенную стипендию?",
  ];
}

export default async function AssistantPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const user = await requireStudent();
  const q = (await searchParams).q?.slice(0, 300) ?? "";
  const msgs = getDb().prepare("SELECT id, role, text, meta, created_at FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT 30").all(user.id).reverse() as Msg[];
  const sum = studySummary(user.id);
  const subjects = retakeSubjects(user.id);
  const lastDraft = [...msgs].reverse().find((m) => m.role === "assistant" && m.meta && JSON.parse(m.meta).draft);
  // Черновик скрываем, если после него студент уже отправил заявку.
  const lastRequestAt = (getDb().prepare("SELECT MAX(created_at) AS t FROM requests WHERE student_id = ?").get(user.id) as { t: string | null }).t;
  const lastDraftId = lastDraft && (!lastRequestAt || lastRequestAt < lastDraft.created_at) ? lastDraft.id : undefined;

  return (
    <>
      <div className="topbar" style={{ justifyContent: "space-between" }}>
        <span className="eyebrow-date">Отвечает по положениям вуза</span>
        {msgs.length > 0 && <form action={clearChatAction}><button className="pillbtn glass">Очистить</button></form>}
      </div>
      <h1 className="large">Помощник</h1>
      <div className="chat" style={{ paddingBottom: 90 }}>
        {msgs.length === 0 && (
          <div className="card">
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <div className="ic" style={{ background: "var(--brand-fill)", color: "#fff" }}><IconSpark /></div>
              <div className="t1">Спросите о пересдачах, справках, стипендии или о своих оценках</div>
            </div>
            <div className="t2" style={{ marginTop: 8 }}>Помощник видит только ваши данные и положения вуза, показывает пункт, на который опирается (его можно раскрыть и прочитать), и может заполнить заявление. Отправляете его вы.</div>
          </div>
        )}
        {msgs.map((m) => {
          if (m.role === "user") return <div key={m.id} className="bub me">{m.text}</div>;
          const meta = (m.meta ? JSON.parse(m.meta) : {}) as Partial<Reply>;
          const rt = meta.draft ? requestType(meta.draft.type) : undefined;
          return (
            <div key={m.id} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div className="bub bot">
                {m.text}
                {meta.sources?.map((s) => {
                  const a = articleBy(s.doc, s.point);
                  return a ? (
                    <details className="src" key={s.point + s.doc}>
                      <summary>{s.doc}, {s.point}</summary>
                      <p><b>{a.title}</b>{a.text}</p>
                    </details>
                  ) : <div className="src" key={s.point + s.doc}>{s.doc}, {s.point}</div>;
                })}
              </div>
              {rt && meta.draft && m.id === lastDraftId && (
                <div className="card">
                  <div className="t2" style={{ fontWeight: 700, textTransform: "uppercase", fontSize: 12, marginBottom: 8 }}>Черновик · {rt.title}</div>
                  <RequestForm rt={rt} subjects={subjects} defaults={meta.draft.details} compact />
                </div>
              )}
            </div>
          );
        })}
        {msgs.length === 0 && (
          <div className="chips" style={{ marginTop: 6 }}>
            {suggestions(user.gender, sum.debts.length > 0).map((s) => <Suggestion key={s} text={s} />)}
          </div>
        )}
      </div>
      <Composer initial={q} />
    </>
  );
}
