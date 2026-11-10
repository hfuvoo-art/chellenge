import AnnounceForm from "@/components/AnnounceForm";
import { requireStaff } from "@/lib/auth";
import { getDb } from "@/lib/db";

export default async function Announce() {
  await requireStaff();
  const groups = (getDb().prepare("SELECT DISTINCT group_name FROM users WHERE role='student' ORDER BY group_name").all() as { group_name: string }[]).map((g) => g.group_name);
  return (
    <>
      <h1 className="large">Новое объявление</h1>
      <div className="card" style={{ maxWidth: 640 }}><AnnounceForm groups={groups} /></div>
    </>
  );
}
