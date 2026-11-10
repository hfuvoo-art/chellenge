import Link from "next/link";
import { logoutAction, resetDemoAction } from "@/app/actions";
import AutoRefresh from "@/components/AutoRefresh";
import GlassLight from "@/components/GlassLight";
import StaffNav from "@/components/StaffNav";
import { requireStaff } from "@/lib/auth";

export default async function StaffLayout({ children }: { children: React.ReactNode }) {
  const u = await requireStaff();
  return (
    <main className="page wide" style={{ paddingBottom: 40 }}>
      <div className="topbar" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="t1">Учебный офис</div>
          <div className="t2">{u.first_name} {u.last_name} · {u.position}</div>
        </div>
        <form action={logoutAction}><button className="pillbtn glass">Выйти</button></form>
      </div>
      <StaffNav />
      {children}
      <details className="reset">
        <summary>Сбросить демо-данные</summary>
        <div className="card">
          <div className="t2">Заявки, расписание, уведомления и чаты вернутся к исходному состоянию. Аккаунты останутся. Данные и так сбрасываются сами каждую ночь в 04:00 по Москве.</div>
          <form action={resetDemoAction} style={{ marginTop: 10 }}><button className="btn danger sm">Да, сбросить сейчас</button></form>
        </div>
      </details>
      <p className="concept">Кабинет сотрудника · концепт для конкурса · данные вымышленные · <Link href="/about" className="link">О проекте</Link></p>
      <AutoRefresh seconds={30} />
      <GlassLight />
    </main>
  );
}
