"use client";
import { useActionState } from "react";
import { saveNotifPrefsAction } from "@/app/actions";

const KINDS = [
  { key: "schedule", label: "Изменения расписания", hint: "Перенос, отмена, новая аудитория" },
  { key: "deadline", label: "Сроки и риски по учёбе", hint: "Напоминания о дедлайнах и недопуске" },
  { key: "announcement", label: "Объявления деканата", hint: "Новости, стипендии, мероприятия" },
];

export default function NotifPrefs({ muted }: { muted: string[] }) {
  const [state, action, pending] = useActionState(saveNotifPrefsAction, undefined);
  return (
    <form action={action} className="card form">
      {KINDS.map((k) => (
        <label key={k.key} className="pref">
          <input type="checkbox" name={k.key} defaultChecked={!muted.includes(k.key)} />
          <span><span className="t1">{k.label}</span><span className="t2">{k.hint}</span></span>
        </label>
      ))}
      <label className="pref">
        <input type="checkbox" checked disabled readOnly />
        <span><span className="t1">Статусы заявок и ответы офиса</span><span className="t2">Всегда включены: это ответы на ваши обращения</span></span>
      </label>
      {state?.ok && <div className="ok-banner" role="status">{state.ok}</div>}
      <button className="btn sm secondary" disabled={pending}>{pending ? "Сохраняем…" : "Сохранить"}</button>
    </form>
  );
}
