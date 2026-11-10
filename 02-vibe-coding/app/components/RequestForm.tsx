"use client";
import { useActionState } from "react";
import { createRequestAction } from "@/app/actions";
import type { RequestType } from "@/lib/request-types";
import SubmitButton from "./SubmitButton";

export default function RequestForm({ rt, subjects, defaults = {}, compact = false }: { rt: RequestType; subjects: string[]; defaults?: Record<string, string>; compact?: boolean }) {
  const [state, action] = useActionState(createRequestAction, undefined);
  return (
    <form action={action} className="form" style={compact ? { gap: 10 } : undefined}>
      <input type="hidden" name="type" value={rt.type} />
      {rt.fields.map((f) => {
        const id = `${rt.type}-${f.name}`;
        const def = defaults[f.name] ?? "";
        return (
          <div className="field" key={f.name}>
            <label htmlFor={id}>{f.label}{"optional" in f && f.optional ? " (необязательно)" : ""}</label>
            {f.kind === "select" && (
              <select id={id} name={f.name} className="input" defaultValue={def || f.options[0]}>
                {f.options.map((o) => <option key={o}>{o}</option>)}
              </select>
            )}
            {f.kind === "subject" && (
              <select id={id} name={f.name} className="input" defaultValue={def || subjects[0]}>
                {subjects.map((o) => <option key={o}>{o}</option>)}
              </select>
            )}
            {f.kind === "number" && <input id={id} name={f.name} type="number" inputMode="numeric" min={f.min} max={f.max} defaultValue={def || f.min} className="input" />}
            {f.kind === "text" && <input id={id} name={f.name} className="input" placeholder={f.placeholder} defaultValue={def} maxLength={300} />}
            {f.kind === "textarea" && <textarea id={id} name={f.name} className="input" placeholder={f.placeholder} defaultValue={def} maxLength={300} />}
          </div>
        );
      })}
      {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
      <SubmitButton>Отправить в деканат</SubmitButton>
    </form>
  );
}
