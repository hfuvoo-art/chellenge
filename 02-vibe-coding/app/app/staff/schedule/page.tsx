import Link from "next/link";
import ClassEditor from "@/components/ClassEditor";
import { requireStaff } from "@/lib/auth";
import { classesOn } from "@/lib/data";
import { getDb } from "@/lib/db";
import { addDays, humanDate, todayMsk } from "@/lib/time";

export const dynamic = "force-dynamic";

export default async function StaffSchedule({ searchParams }: { searchParams: Promise<{ g?: string; d?: string }> }) {
  await requireStaff();
  const sp = await searchParams;
  const groups = (getDb().prepare("SELECT DISTINCT group_name FROM users WHERE role='student' ORDER BY group_name").all() as { group_name: string }[]).map((g) => g.group_name);
  const group = groups.includes(sp.g ?? "") ? sp.g! : groups[0];
  const date = sp.d && /^\d{4}-\d{2}-\d{2}$/.test(sp.d) ? sp.d : todayMsk();
  const list = classesOn(group, date);
  return (
    <>
      <h1 className="large">Изменения в расписании</h1>
      <div className="seg glass" style={{ maxWidth: 360 }}>
        {groups.map((g) => <Link key={g} href={`/staff/schedule?g=${g}&d=${date}`} aria-current={g === group ? "page" : undefined}>{g}</Link>)}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "8px 0" }}>
        <Link className="btn sm secondary" href={`/staff/schedule?g=${group}&d=${addDays(date, -1)}`} aria-label="Предыдущий день">‹</Link>
        <span className="t1" style={{ flex: 1, textAlign: "center" }}>{humanDate(date)}</span>
        <Link className="btn sm secondary" href={`/staff/schedule?g=${group}&d=${addDays(date, 1)}`} aria-label="Следующий день">›</Link>
      </div>
      <p className="t2" style={{ padding: "0 6px 10px" }}>Любое изменение сразу появится у студентов группы на главной и в уведомлениях.</p>
      {list.length ? (
        <div className="grid2">{list.map((c) => <ClassEditor key={c.id} c={c} />)}</div>
      ) : (
        <div className="card empty"><div className="t1">В этот день пар нет</div></div>
      )}
    </>
  );
}
