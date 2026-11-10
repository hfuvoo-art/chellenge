import Link from "next/link";
import { requireStaff } from "@/lib/auth";
import { getDb } from "@/lib/db";
import { STATUS_LABEL } from "@/lib/request-types";
import { relativeTime } from "@/lib/time";

export const dynamic = "force-dynamic";
const BADGE: Record<string, string> = { submitted: "b-gray", in_progress: "b-brand", ready: "b-ok", rejected: "b-bad" };
const FILTERS = [
  { key: "new", label: "Новые", where: "r.status = 'submitted'" },
  { key: "work", label: "В работе", where: "r.status = 'in_progress'" },
  { key: "done", label: "Закрытые", where: "r.status IN ('ready','rejected')" },
];

export default async function StaffQueue({ searchParams }: { searchParams: Promise<{ f?: string }> }) {
  await requireStaff();
  const fk = (await searchParams).f ?? "new";
  const filter = FILTERS.find((f) => f.key === fk) ?? FILTERS[0];
  const db = getDb();
  const counts = Object.fromEntries(FILTERS.map((f) => [f.key, (db.prepare(`SELECT COUNT(*) n FROM requests r WHERE ${f.where}`).get() as { n: number }).n]));
  const rows = db.prepare(`SELECT r.id, r.number, r.title, r.status, r.created_at, r.updated_at, u.last_name, u.first_name, u.group_name
    FROM requests r JOIN users u ON u.id = r.student_id WHERE ${filter.where} ORDER BY r.created_at ${fk === "done" ? "DESC" : "ASC"}`).all() as
    { id: number; number: number; title: string; status: string; created_at: string; updated_at: string; last_name: string; first_name: string; group_name: string }[];
  return (
    <>
      <h1 className="large">Заявки студентов</h1>
      <div className="seg glass" style={{ maxWidth: 480 }}>
        {FILTERS.map((f) => <Link key={f.key} href={`/staff?f=${f.key}`} aria-current={f.key === filter.key ? "page" : undefined}>{f.label} · {counts[f.key]}</Link>)}
      </div>
      {rows.length ? (
        <div className="card list" style={{ marginTop: 10 }}>
          {rows.map((r) => (
            <Link key={r.id} href={`/staff/requests/${r.id}`} className="cell">
              <div className="g">
                <div className="t1">{r.title} · № {r.number}</div>
                <div className="t2">{r.last_name} {r.first_name} · {r.group_name} · подана {relativeTime(r.created_at)}</div>
              </div>
              <span className={`badge ${BADGE[r.status]}`}>{STATUS_LABEL[r.status]}</span>
              <span className="chev">›</span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="card empty" style={{ marginTop: 10 }}><div className="t1">Очередь пуста</div><div className="t2">Новые заявки появятся здесь автоматически</div></div>
      )}
    </>
  );
}
