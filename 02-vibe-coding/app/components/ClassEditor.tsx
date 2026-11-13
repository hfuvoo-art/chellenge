"use client";
import { useActionState } from "react";
import { changeClassAction } from "@/app/actions";
import type { ClassRow } from "@/lib/data";
import { roomLabel } from "@/lib/format";

export default function ClassEditor({ c }: { c: ClassRow }) {
  const [state, action, pending] = useActionState(changeClassAction, undefined);
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <div>
          <div className="t1">{c.start}–{c.end} · {c.subject}</div>
          <div className="t2">{c.kind} · {c.status === "moved" && c.old_room ? `${roomLabel(c.old_room)} → ${roomLabel(c.room)}` : roomLabel(c.room)} · {c.teacher}</div>
        </div>
        {c.status === "cancelled" && <span className="badge b-bad">Отменена</span>}
        {c.status === "moved" && <span className="badge b-warn">Изменена</span>}
      </div>
      <form action={action} className="form" style={{ marginTop: 10, gap: 8 }}>
        <input type="hidden" name="id" value={c.id} />
        <div style={{ display: "flex", gap: 8 }}>
          <input name="room" className="input" placeholder="Новая аудитория" aria-label="Новая аудитория" maxLength={40} />
          <button name="action" value="room" className="btn sm" disabled={pending}>Сменить</button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input name="start" className="input" placeholder="Новое время, ЧЧ:ММ" aria-label="Новое время начала" inputMode="numeric" pattern="[0-2][0-9]:[0-5][0-9]" />
          <button name="action" value="time" className="btn sm" disabled={pending}>Перенести</button>
        </div>
        <div className="row-btns">
          {c.status !== "cancelled" && <button name="action" value="cancel" className="btn sm danger" disabled={pending}>Отменить пару</button>}
          {c.status !== "ok" && <button name="action" value="restore" className="btn sm secondary" disabled={pending}>Вернуть как было</button>}
        </div>
        {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
        {state?.ok && <div className="ok-banner" role="status">{state.ok}</div>}
      </form>
    </div>
  );
}
