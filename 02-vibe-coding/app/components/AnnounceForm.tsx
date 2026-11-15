"use client";
import { useActionState } from "react";
import { announceAction } from "@/app/actions";
import SubmitButton from "./SubmitButton";

export default function AnnounceForm({ groups }: { groups: string[] }) {
  const [state, action] = useActionState(announceAction, undefined);
  return (
    <form action={action} className="form">
      <div className="field"><label htmlFor="title">Заголовок</label><input id="title" name="title" className="input" maxLength={120} required /></div>
      <div className="field"><label htmlFor="body">Текст</label><textarea id="body" name="body" className="input" maxLength={1000} required /></div>
      <div className="field">
        <label htmlFor="audience">Кому</label>
        <select id="audience" name="audience" className="input">
          <option value="all">Всем студентам</option>
          {groups.map((g) => <option key={g} value={g}>Группа {g}</option>)}
        </select>
      </div>
      {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
      {state?.ok && <div className="ok-banner" role="status">{state.ok}</div>}
      <SubmitButton>Опубликовать</SubmitButton>
    </form>
  );
}
