"use client";
import { useActionState } from "react";
import { setRequestStatusAction } from "@/app/actions";

const NEXT: Record<string, { status: string; label: string; cls: string }[]> = {
  submitted: [{ status: "in_progress", label: "Взять в работу", cls: "btn" }, { status: "rejected", label: "Отклонить", cls: "btn danger" }],
  in_progress: [{ status: "ready", label: "Готово", cls: "btn" }, { status: "rejected", label: "Отклонить", cls: "btn danger" }],
};

export default function StatusForm({ id, status }: { id: number; status: string }) {
  const [state, action, pending] = useActionState(setRequestStatusAction, undefined);
  const options = NEXT[status] ?? [];
  if (!options.length) return state?.ok ? <div className="ok-banner" role="status">{state.ok}</div> : <div className="t2">Заявка закрыта.</div>;
  return (
    <form action={action} className="form">
      <input type="hidden" name="id" value={id} />
      <div className="field">
        <label htmlFor="comment">Комментарий студенту</label>
        <textarea id="comment" name="comment" className="input" placeholder={status === "in_progress" ? "Например: заберите в каб. 112 с паспортом" : "Обязателен при отказе"} maxLength={500} />
      </div>
      {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
      {state?.ok && <div className="ok-banner" role="status">{state.ok}</div>}
      <div className="row-btns">
        {options.map((o) => (
          <button key={o.status} name="status" value={o.status} className={`${o.cls} sm`} disabled={pending} style={{ flex: 1 }}
            onClick={o.status === "rejected" ? (e) => { if (!window.confirm("Отклонить заявку? Студент получит уведомление с причиной, вернуть заявку в работу будет нельзя.")) e.preventDefault(); } : undefined}>
            {o.label}
          </button>
        ))}
      </div>
    </form>
  );
}
