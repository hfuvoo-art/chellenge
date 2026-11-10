import Link from "next/link";
import { logoutAction } from "@/app/actions";
import { IconBack } from "@/components/icons";
import { requireStudent } from "@/lib/auth";

export default async function ProfilePage() {
  const u = await requireStudent();
  return (
    <>
      <div className="topbar"><Link href="/" className="pillbtn glass"><IconBack /> Сегодня</Link></div>
      <div style={{ display: "flex", gap: 14, alignItems: "center", padding: "6px 6px 16px" }}>
        <div aria-hidden style={{ width: 64, height: 64, borderRadius: "50%", background: "var(--brand)", color: "#fff", display: "grid", placeItems: "center", fontSize: 22, fontWeight: 800 }}>{u.first_name[0]}{u.last_name[0]}</div>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em" }}>{u.last_name} {u.first_name}</h1>
          <div className="t2">{u.middle_name}</div>
        </div>
      </div>
      <div className="stack">
        <div className="card">
          <div className="kv"><span>Факультет</span><span>{u.faculty}</span></div>
          <div className="kv"><span>Направление</span><span>{u.program}</span></div>
          <div className="kv"><span>Курс</span><span>{u.course}</span></div>
          <div className="kv"><span>Группа</span><span>{u.group_name}</span></div>
          <div className="kv"><span>Студенческий билет</span><span>{u.student_card}</span></div>
          <div className="kv"><span>Почта</span><span>{u.email}</span></div>
        </div>
        <div className="sh">Безопасность</div>
        <div className="card t2" style={{ lineHeight: 1.5 }}>
          Вы видите только свои данные: сервер проверяет владельца при каждом запросе. Пароль хранится в виде хэша, вход длится 7 дней и завершается кнопкой ниже.
        </div>
        <form action={logoutAction}><button className="btn danger">Выйти</button></form>
        <p className="concept">Концепт для конкурса MGIMO×AI Challenge 2026 · не официальный сервис · данные вымышленные</p>
      </div>
    </>
  );
}
