import Link from "next/link";
import { redirect } from "next/navigation";
import { IconCalendar, IconChart, IconDoc, IconSpark } from "@/components/icons";
import { currentUser } from "@/lib/auth";
import LoginForm from "./LoginForm";

const FEATURES = [
  { Icon: IconCalendar, title: "Расписание с изменениями", text: "Перенос или новая аудитория видны на главной и приходят уведомлением." },
  { Icon: IconDoc, title: "Справка за два касания", text: "Заявка онлайн, статус по шагам, готовая справка с QR-кодом проверки." },
  { Icon: IconChart, title: "Учёба без сюрпризов", text: "Баллы, прогноз оценок и риски: что сдать, чтобы не потерять допуск и стипендию." },
  { Icon: IconSpark, title: "Помощник по положениям", text: "Отвечает со ссылкой на пункт и сам заполняет заявление. Отправляете его вы." },
];

export default async function LoginPage() {
  const u = await currentUser();
  if (u) redirect(u.role === "staff" ? "/staff" : "/");
  return (
    <main className="page landing">
      <div className="cols">
        <section className="l-head">
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 6px 6px" }}>
            <div aria-hidden className="logo-lg">Д</div>
            <div>
              <div className="t1">Мой деканат</div>
              <div className="t2">Концепт для MGIMO×AI Challenge 2026</div>
            </div>
          </div>
          <h1 className="large" style={{ paddingTop: 18 }}>Деканат, который отвечает</h1>
          <p className="lead">Личный кабинет студента: вместо очереди в деканат и десяти чатов — один экран, где видно, что происходит сегодня и что нужно сделать.</p>
        </section>
        <section className="l-login">
          <h2 className="h" style={{ padding: "0 6px 10px" }}>Вход</h2>
          <LoginForm />
        </section>
        <section className="l-feat">
          <ul className="features">
            {FEATURES.map(({ Icon, title, text }) => (
              <li key={title}>
                <div className="ic" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><Icon /></div>
                <div><div className="t1">{title}</div><div className="t2">{text}</div></div>
              </li>
            ))}
          </ul>
          <p className="t2" style={{ padding: "4px 6px 0" }}>Есть и вторая сторона: кабинет учебного офиса, где заявки берут в работу и меняют расписание. <Link href="/about" className="link">О проекте</Link></p>
        </section>
      </div>
      <p className="concept">Не официальный сервис вуза. Все данные вымышленные.</p>
    </main>
  );
}
