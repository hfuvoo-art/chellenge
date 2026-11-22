"use client";
import { useActionState, useState } from "react";
import { createRequestAction } from "@/app/actions";
import type { RequestType } from "@/lib/request-types";
import SubmitButton from "./SubmitButton";

const MAX = 300;

/** Поле с счётчиком символов: видно, сколько осталось до лимита. */
function Counted({ id, name, placeholder, def, area }: { id: string; name: string; placeholder?: string; def: string; area: boolean }) {
  const [n, setN] = useState(def.length);
  const props = { id, name, className: "input", placeholder, defaultValue: def, maxLength: MAX, "aria-describedby": `${id}-n`, onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setN(e.target.value.length) };
  return (
    <>
      {area ? <textarea {...props} /> : <input {...props} />}
      <div id={`${id}-n`} className={`counter ${n >= MAX ? "full" : ""}`}>{n}/{MAX}</div>
    </>
  );
}

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
              <select id={id} name={f.name} className="input" defaultValue={def || (f.choose ? "" : f.options[0])} required>
                {f.choose && <option value="" disabled>Выберите…</option>}
                {f.options.map((o) => <option key={o}>{o}</option>)}
              </select>
            )}
            {f.kind === "subject" && (
              <select id={id} name={f.name} className="input" defaultValue={subjects.includes(def) ? def : ""} required>
                <option value="" disabled>Выберите дисциплину…</option>
                {subjects.map((o) => <option key={o}>{o}</option>)}
              </select>
            )}
            {f.kind === "number" && <input id={id} name={f.name} type="number" inputMode="numeric" min={f.min} max={f.max} defaultValue={def || f.min} className="input" />}
            {f.kind === "text" && <input id={id} name={f.name} className="input" placeholder={f.placeholder} defaultValue={def} maxLength={MAX} />}
            {f.kind === "textarea" && <Counted id={id} name={f.name} placeholder={f.placeholder} def={def} area />}
          </div>
        );
      })}
      {state?.error && <div className="err-banner" role="alert">{state.error}</div>}
      <SubmitButton>Отправить в деканат</SubmitButton>
    </form>
  );
}
