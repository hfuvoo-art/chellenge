import { redirect } from "next/navigation";
import { currentUser } from "@/lib/auth";
import LoginForm from "./LoginForm";

export default async function LoginPage() {
  const u = await currentUser();
  if (u) redirect(u.role === "staff" ? "/staff" : "/");
  return (
    <main className="page" style={{ paddingTop: 48, paddingBottom: 40 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 6px 6px" }}>
        <div aria-hidden style={{ width: 48, height: 48, borderRadius: 15, background: "var(--brand)", color: "#fff", display: "grid", placeItems: "center", fontWeight: 800, fontSize: 20 }}>Д</div>
        <div>
          <div className="t1">Мой деканат</div>
          <div className="t2">Деканат, который отвечает</div>
        </div>
      </div>
      <h1 className="large" style={{ paddingTop: 18 }}>Вход</h1>
      <div className="card">
        <LoginForm />
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <div className="t1">Тестовые аккаунты</div>
        <div className="kv"><span>Студентка 2 курса</span><span>alina / demo2026</span></div>
        <div className="kv"><span>Студент 4 курса</span><span>timur / demo2026</span></div>
        <div className="kv"><span>Учебный офис</span><span>dekanat / staff2026</span></div>
      </div>
      <p className="concept">Концепт для конкурса MGIMO×AI Challenge 2026. Не официальный сервис вуза, все данные вымышленные.</p>
    </main>
  );
}
