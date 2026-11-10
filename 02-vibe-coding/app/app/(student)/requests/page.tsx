import Link from "next/link";
import { IconDoc, IconPlus } from "@/components/icons";
import TopBar from "@/components/TopBar";
import { requireStudent } from "@/lib/auth";
import { requestsOf } from "@/lib/data";
import { REQUEST_TYPES, STATUS_LABEL } from "@/lib/request-types";
import { relativeTime } from "@/lib/time";

export const dynamic = "force-dynamic";

const BADGE: Record<string, string> = { submitted: "b-gray", in_progress: "b-brand", ready: "b-ok", rejected: "b-bad" };

export default async function RequestsPage() {
  const user = await requireStudent();
  const list = requestsOf(user.id);
  const active = list.filter((r) => r.status === "submitted" || r.status === "in_progress");
  const done = list.filter((r) => r.status === "ready" || r.status === "rejected");
  return (
    <>
      <TopBar user={user} left={<span className="eyebrow-date">Справки и заявления</span>} />
      <h1 className="large">Заявки</h1>
      <div className="stack">
        <div className="sh">Заказать за 2 касания</div>
        <div className="card list">
          {REQUEST_TYPES.map((t) => (
            <Link key={t.type} href={`/requests/new?type=${t.type}`} className="cell">
              <div className="ic" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><IconDoc /></div>
              <div className="g"><div className="t1">{t.title}</div><div className="t2">Срок: {t.eta}</div></div>
              <span style={{ color: "var(--brand)" }}><IconPlus /></span>
            </Link>
          ))}
        </div>

        <div className="sh">В работе</div>
        {active.length ? (
          <div className="card list">{active.map((r) => <Row key={r.id} r={r} />)}</div>
        ) : (
          <div className="card empty">
            <div className="ill"><IconDoc /></div>
            <div className="t1">Активных заявок нет</div>
            <div className="t2">Выберите справку выше или попросите помощника заполнить заявление</div>
          </div>
        )}

        {done.length > 0 && (
          <>
            <div className="sh">Готовые и закрытые</div>
            <div className="card list">{done.map((r) => <Row key={r.id} r={r} />)}</div>
          </>
        )}
      </div>
    </>
  );
}

function Row({ r }: { r: ReturnType<typeof requestsOf>[number] }) {
  const step = { submitted: 1, in_progress: 2, ready: 3, rejected: 3 }[r.status];
  return (
    <Link href={`/requests/${r.number}`} className="cell">
      <div className="g">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
          <span className="t1">{r.title}</span>
          <span className={`badge ${BADGE[r.status]}`}>{STATUS_LABEL[r.status]}</span>
        </div>
        <div className="steps" aria-hidden>{[1, 2, 3].map((i) => <i key={i} className={i <= step ? (r.status === "rejected" ? "bad" : "on") : ""} />)}</div>
        <div className="t2" style={{ marginTop: 6 }}>№ {r.number} · обновлено {relativeTime(r.updated_at)}</div>
      </div>
    </Link>
  );
}
