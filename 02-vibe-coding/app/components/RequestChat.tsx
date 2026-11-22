"use client";
import { useActionState, useEffect, useRef } from "react";
import { sendRequestMessageAction } from "@/app/actions";

export type ChatMsg = { id: number; author: "student" | "staff"; author_name: string; text: string; when: string };

/** Переписка по заявке. side — кто сейчас смотрит: свои сообщения справа. */
export default function RequestChat({ side, target, messages, closed = false }: { side: "student" | "staff"; target: number; messages: ChatMsg[]; closed?: boolean }) {
  const [state, action, pending] = useActionState(sendRequestMessageAction, undefined);
  const ref = useRef<HTMLFormElement>(null);
  useEffect(() => { if (state?.ok) ref.current?.reset(); }, [state]);
  return (
    <div className="card" id="chat">
      {messages.length === 0 ? (
        <div className="t2">{side === "student" ? "Есть вопрос по этой заявке? Напишите, сотрудник учебного офиса ответит здесь же." : "Студент пока ничего не писал. Можно написать первым, например уточнить данные."}</div>
      ) : (
        <div className="chat rchat" role="log" aria-label="Переписка по заявке">
          {messages.map((m) => (
            <div key={m.id} className={`rmsg ${m.author === side ? "mine" : ""}`}>
              <div className={`bub ${m.author === side ? "me" : "other"}`}>{m.text}</div>
              <div className="rmeta">{m.author === side ? "Вы" : m.author_name} · {m.when}</div>
            </div>
          ))}
        </div>
      )}
      <form action={action} ref={ref} className="form" style={{ marginTop: 12 }}>
        <input type="hidden" name="side" value={side} />
        <input type="hidden" name={side === "staff" ? "id" : "number"} value={target} />
        <div className="field">
          <label htmlFor="rchat-text">{side === "student" ? "Сообщение учебному офису" : "Ответ студенту"}</label>
          <textarea id="rchat-text" name="text" className="input" maxLength={500} required placeholder={side === "student" ? (closed ? "Заявка закрыта, но спросить всё ещё можно" : "Например: можно ли забрать справку в пятницу?") : "Ответ увидит только этот студент"} style={{ minHeight: 64 }} />
        </div>
        {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
        {state?.ok && <div className="ok-banner" role="status">{state.ok}</div>}
        <button className="btn sm" disabled={pending}>{pending ? "Отправляем…" : "Отправить"}</button>
      </form>
    </div>
  );
}
