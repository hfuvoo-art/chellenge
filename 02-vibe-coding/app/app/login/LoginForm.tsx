"use client";
import { useActionState, useState } from "react";
import { loginAction } from "@/app/actions";
import SubmitButton from "@/components/SubmitButton";

const ACCOUNTS = [
  { who: "Студентка 2 курса", login: "alina", password: "demo2026" },
  { who: "Студент 4 курса", login: "timur", password: "demo2026" },
  { who: "Учебный офис", login: "dekanat", password: "staff2026" },
];

export default function LoginForm() {
  const [state, action, pending] = useActionState(loginAction, undefined);
  const [show, setShow] = useState(false);
  const enter = (login: string, password: string) => {
    const form = document.getElementById("login-form") as HTMLFormElement | null;
    if (!form) return;
    (form.elements.namedItem("login") as HTMLInputElement).value = login;
    (form.elements.namedItem("password") as HTMLInputElement).value = password;
    form.requestSubmit();
  };
  return (
    <>
      <div className="card">
        <form action={action} className="form" noValidate id="login-form">
          <div className="field">
            <label htmlFor="login">Логин</label>
            <input id="login" name="login" className="input" autoComplete="username" autoCapitalize="none" spellCheck={false} required defaultValue={state?.login ?? ""} />
          </div>
          <div className="field">
            <label htmlFor="password">Пароль</label>
            <div className="passwrap">
              <input id="password" name="password" type={show ? "text" : "password"} className="input" autoComplete="current-password" required />
              <button type="button" className="passtoggle" onClick={() => setShow((v) => !v)} aria-pressed={show} aria-label={show ? "Скрыть пароль" : "Показать пароль"}>
                {show ? "Скрыть" : "Показать"}
              </button>
            </div>
          </div>
          {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
          <SubmitButton pendingText="Входим…">Войти</SubmitButton>
          <details className="forgot">
            <summary>Забыли пароль?</summary>
            <p>Пароль восстанавливает учебный офис: каб. 112, по будням с 10:00 до 17:00, с собой студенческий билет. В этом концепте просто выберите тестовый аккаунт ниже.</p>
          </details>
        </form>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <div className="t1">Тестовые аккаунты</div>
        <div className="t2" style={{ marginBottom: 6 }}>Нажмите на строку, чтобы войти сразу</div>
        {ACCOUNTS.map((a) => (
          <button key={a.login} type="button" className="acc" onClick={() => enter(a.login, a.password)} disabled={pending}>
            <span>{a.who}</span>
            <span><b>{a.login}</b> / {a.password} <i aria-hidden>›</i></span>
          </button>
        ))}
      </div>
    </>
  );
}
