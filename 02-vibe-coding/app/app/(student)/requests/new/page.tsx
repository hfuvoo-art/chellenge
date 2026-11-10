import Link from "next/link";
import { redirect } from "next/navigation";
import { IconBack } from "@/components/icons";
import RequestForm from "@/components/RequestForm";
import { requireStudent } from "@/lib/auth";
import { studySummary } from "@/lib/data";
import { requestType } from "@/lib/request-types";

export default async function NewRequestPage({ searchParams }: { searchParams: Promise<{ type?: string }> }) {
  const user = await requireStudent();
  const rt = requestType((await searchParams).type ?? "");
  if (!rt) redirect("/requests");
  const sum = studySummary(user.id);
  const subjects = [...sum.debts.map((d) => d.name), ...sum.current.map((s) => s.name)];
  return (
    <>
      <div className="topbar"><Link href="/requests" className="pillbtn glass"><IconBack /> Заявки</Link></div>
      <h1 className="large" style={{ fontSize: 28 }}>{rt.title}</h1>
      <div className="stack">
        <p className="t2" style={{ padding: "0 6px" }}>{rt.description} Срок: {rt.eta}.</p>
        <div className="card">
          <div className="kv"><span>Студент</span><span>{user.last_name} {user.first_name[0]}. {user.middle_name[0]}.</span></div>
          <div className="kv"><span>Группа</span><span>{user.group_name}</span></div>
        </div>
        {rt.type === "scholarship_plus" && !sum.scholarship && (
          <div className="alert" style={{ marginTop: 0 }}>
            <span>Сейчас условие не выполнено: {sum.scholarshipReasons.map((r) => r.text).join("; ")}. Заявление подать можно, но офис, скорее всего, отклонит его, пока это не закрыто.</span>
          </div>
        )}
        <div className="card"><RequestForm rt={rt} subjects={subjects} /></div>
      </div>
    </>
  );
}
