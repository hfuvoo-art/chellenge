import { logoutAction } from "@/app/actions";
import AutoRefresh from "@/components/AutoRefresh";
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
      <p className="concept">Кабинет сотрудника · концепт для конкурса · данные вымышленные</p>
      <AutoRefresh seconds={30} />
    </main>
  );
}
