import Link from "next/link";
import { notFound } from "next/navigation";
import { IconBack, IconCheck } from "@/components/icons";
import { requireStudent } from "@/lib/auth";
import { requestOf } from "@/lib/data";
import { requestType, STATUS_LABEL } from "@/lib/request-types";
import { relativeTime } from "@/lib/time";

export const dynamic = "force-dynamic";
const BADGE: Record<string, string> = { submitted: "b-gray", in_progress: "b-brand", ready: "b-ok", rejected: "b-bad" };

export default async function RequestPage({ params, searchParams }: { params: Promise<{ number: string }>; searchParams: Promise<{ new?: string }> }) {
  const user = await requireStudent();
  const number = Number((await params).number);
  const isNew = (await searchParams).new === "1";
  // Заявку ищем по номеру И владельцу. Чужой номер в адресе даёт 404, а не чужие данные.
  const r = Number.isInteger(number) ? requestOf(user.id, number) : null;
  if (!r) notFound();
  const rt = requestType(r.type);
  const details = JSON.parse(r.details) as Record<string, string>;
  const step = { submitted: 1, in_progress: 2, ready: 3, rejected: 3 }[r.status];

  return (
    <>
      <div className="topbar"><Link href="/requests" className="pillbtn glass"><IconBack /> Заявки</Link></div>
      <h1 className="large" style={{ fontSize: 28 }}>{r.title}</h1>
      <div className="stack">
        {isNew && <div className="ok-banner" role="status">Заявка № {r.number} отправлена. Статус придёт в уведомления.</div>}
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="t1">Заявка № {r.number}</span>
            <span className={`badge ${BADGE[r.status]}`}>{STATUS_LABEL[r.status]}</span>
          </div>
          <div className="steps" aria-hidden>{[1, 2, 3].map((i) => <i key={i} className={i <= step ? (r.status === "rejected" ? "bad" : "on") : ""} />)}</div>
          <div className="t2" style={{ marginTop: 8 }}>
            {r.status === "submitted" && `Ждёт учебный офис. Обычный срок: ${rt?.eta ?? "несколько дней"}.`}
            {r.status === "in_progress" && "Учебный офис готовит документ."}
            {r.status === "ready" && (r.staff_comment ?? "Заявка выполнена.")}
            {r.status === "rejected" && `Отклонена: ${r.staff_comment}`}
          </div>
          {r.status === "ready" && r.verify_code && (
            <Link href={`/requests/${r.number}/certificate`} className="btn" style={{ marginTop: 12 }}><IconCheck /> Открыть справку</Link>
          )}
        </div>

        <div className="sh">Данные заявки</div>
        <div className="card">
          {rt?.fields.map((f) => details[f.name] ? <div className={`kv ${details[f.name].length > 28 ? "long" : ""}`} key={f.name}><span>{f.label}</span><span>{details[f.name]}</span></div> : null)}
        </div>

        <div className="sh">История</div>
        <div className="card">
          <ol className="timeline">
            {r.events.map((e) => (
              <li key={e.id} className={e.status === "rejected" ? "rejected" : ""}>
                <div className="t1">{STATUS_LABEL[e.status]}</div>
                <div className="t2">{e.actor} · {relativeTime(e.created_at)}</div>
                {e.comment && <div className="t2">{e.comment}</div>}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </>
  );
}
