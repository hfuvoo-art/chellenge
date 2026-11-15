import Link from "next/link";
import { logoutAction, resetDemoAction } from "@/app/actions";
import AutoRefresh from "@/components/AutoRefresh";
import GlassLight from "@/components/GlassLight";
import TabBar, { type TabItem } from "@/components/TabBar";
import { requireStaff } from "@/lib/auth";

const ITEMS: TabItem[] = [
  { href: "/staff", label: "Заявки", icon: "doc", exact: true, also: ["/staff/requests"] },
  { href: "/staff/schedule", label: "Расписание", icon: "calendar" },
  { href: "/staff/announce", label: "Объявление", icon: "megaphone" },
];

export default async function StaffLayout({ children }: { children: React.ReactNode }) {
  const u = await requireStaff();
  return (
    <>
      <TabBar
        items={ITEMS}
        assistant={false}
        brandSub="Учебный офис"
        userHref={null}
        name={`${u.first_name} ${u.last_name}`}
        sub={u.position ?? "Учебный офис"}
        initials={`${u.first_name[0]}${u.last_name[0]}`}
      />
      <main className="page shell wide">
        <div className="topbar">
          <div className="eyebrow-date">Учебный офис · {u.first_name} {u.last_name}</div>
          <form action={logoutAction}><button className="pillbtn glass">Выйти</button></form>
        </div>
        {children}
        <details className="reset">
          <summary>Сбросить демо-данные</summary>
          <div className="card">
            <div className="t2">Заявки, расписание, уведомления и чаты вернутся к исходному состоянию. Аккаунты останутся. Данные и так сбрасываются сами каждую ночь в 04:00 по Москве.</div>
            <form action={resetDemoAction} style={{ marginTop: 10 }}><button className="btn danger sm">Да, сбросить сейчас</button></form>
          </div>
        </details>
        <p className="concept">Кабинет сотрудника · концепт для конкурса · данные вымышленные · <Link href="/about" className="link">О проекте</Link></p>
      </main>
      <AutoRefresh seconds={30} />
      <GlassLight />
    </>
  );
}
