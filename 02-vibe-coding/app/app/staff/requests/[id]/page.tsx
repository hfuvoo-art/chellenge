import Link from "next/link";
import { notFound } from "next/navigation";
import { IconBack } from "@/components/icons";
import StatusForm from "@/components/StatusForm";
import { requireStaff } from "@/lib/auth";
import type { RequestEvent, RequestRow } from "@/lib/data";
import { getDb } from "@/lib/db";
import { requestType, STATUS_LABEL } from "@/lib/request-types";
import { relativeTime } from "@/lib/time";

export const dynamic = "force-dynamic";

export default async function StaffRequest({ params }: { params: Promise<{ id: string }> }) {
  await requireStaff();
  const id = Number((await params).id);
  const db = getDb();
  const r = db.prepare("SELECT r.*, u.last_name, u.first_name, u.middle_name, u.group_name, u.course, u.program, u.student_card FROM requests r JOIN users u ON u.id = r.student_id WHERE r.id = ?").get(id) as
    | (RequestRow & { last_name: string; first_name: string; middle_name: string; group_name: string; course: number; program: string; student_card: string }) | undefined;
  if (!r) notFound();
  const events = db.prepare("SELECT * FROM request_events WHERE request_id = ? ORDER BY created_at, id").all(r.id) as RequestEvent[];
  const rt = requestType(r.type);
  const details = JSON.parse(r.details) as Record<string, string>;
  return (
    <>
      <Link href="/staff" className="pillbtn glass"><IconBack /> Очередь</Link>
      <h1 className="large" style={{ fontSize: 28, paddingTop: 10 }}>{r.title} · № {r.number}</h1>
      <div className="grid2">
        <div className="stack">
          <div className="card">
            <div className="kv"><span>Студент</span><span>{r.last_name} {r.first_name} {r.middle_name}</span></div>
            <div className="kv"><span>Группа, курс</span><span>{r.group_name}, {r.course} курс</span></div>
            <div className="kv"><span>Направление</span><span>{r.program}</span></div>
            <div className="kv"><span>Студ. билет</span><span>{r.student_card}</span></div>
          </div>
          <div className="card">
            {rt?.fields.map((f) => details[f.name] ? <div className="kv" key={f.name}><span>{f.label}</span><span>{details[f.name]}</span></div> : null)}
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <div className="t1" style={{ marginBottom: 10 }}>Статус: {STATUS_LABEL[r.status]}</div>
            <StatusForm id={r.id} status={r.status} />
          </div>
          <div className="card">
            <ol className="timeline">
              {events.map((e) => <li key={e.id} className={e.status === "rejected" ? "rejected" : ""}><div className="t1">{STATUS_LABEL[e.status]}</div><div className="t2">{e.actor} · {relativeTime(e.created_at)}</div>{e.comment && <div className="t2">{e.comment}</div>}</li>)}
            </ol>
          </div>
        </div>
      </div>
    </>
  );
}
