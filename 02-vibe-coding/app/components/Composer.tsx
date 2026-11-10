"use client";
import { useActionState, useEffect, useRef } from "react";
import { useFormStatus } from "react-dom";
import { askAssistantAction } from "@/app/actions";
import { IconSend } from "./icons";

function SendBtn() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" aria-label="Отправить" disabled={pending}>
      {pending ? <span className="typing" aria-label="Помощник думает"><i /><i /><i /></span> : <IconSend />}
    </button>
  );
}

function Pending() {
  const { pending, data } = useFormStatus();
  useEffect(() => { if (pending) window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); }, [pending]);
  if (!pending) return null;
  return (
    <div style={{ position: "fixed", bottom: 160, left: 0, right: 0, display: "flex", justifyContent: "center", pointerEvents: "none" }}>
      <div style={{ width: "min(560px,100%)", padding: "0 14px", display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="bub me" style={{ alignSelf: "flex-end" }}>{String(data?.get("text") ?? "")}</div>
        <div className="bub bot"><span className="typing" aria-label="Помощник думает"><i /><i /><i /></span></div>
      </div>
    </div>
  );
}

export default function Composer({ initial = "" }: { initial?: string }) {
  const [state, action] = useActionState(askAssistantAction, undefined);
  const ref = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (state?.ok) { ref.current?.reset(); window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); }
  }, [state]);
  useEffect(() => { window.scrollTo({ top: document.body.scrollHeight }); }, []);
  return (
    <div className="composer">
      <form ref={ref} action={action} id="composer">
        <div className="glass">
          <label htmlFor="ask" className="sr">Вопрос помощнику</label>
          <input id="ask" name="text" placeholder="Спросите помощника…" defaultValue={initial} maxLength={500} autoComplete="off" />
          <SendBtn />
        </div>
        <Pending />
      </form>
      {state?.error && <div className="err-banner" role="alert" style={{ position: "fixed", bottom: 170 }}>{state.error}</div>}
    </div>
  );
}

export function Suggestion({ text }: { text: string }) {
  return (
    <button type="button" className="chip" onClick={() => {
      const input = document.getElementById("ask") as HTMLInputElement | null;
      const form = document.getElementById("composer") as HTMLFormElement | null;
      if (input && form) { input.value = text; form.requestSubmit(); }
    }}>{text}</button>
  );
}
