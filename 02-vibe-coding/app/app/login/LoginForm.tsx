"use client";
import { useActionState } from "react";
import { loginAction } from "@/app/actions";
import SubmitButton from "@/components/SubmitButton";

export default function LoginForm() {
  const [state, action] = useActionState(loginAction, undefined);
  return (
    <form action={action} className="form" noValidate>
      <div className="field">
        <label htmlFor="login">Логин</label>
        <input id="login" name="login" className="input" autoComplete="username" autoCapitalize="none" spellCheck={false} required />
      </div>
      <div className="field">
        <label htmlFor="password">Пароль</label>
        <input id="password" name="password" type="password" className="input" autoComplete="current-password" required />
      </div>
      {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
      <SubmitButton pendingText="Входим…">Войти</SubmitButton>
    </form>
  );
}
