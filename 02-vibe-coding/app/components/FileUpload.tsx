"use client";
import { useActionState, useState } from "react";
import { uploadRequestFileAction } from "@/app/actions";

const MAX = 2 * 1024 * 1024;

/** Прикрепить документ к заявке: PDF, JPG или PNG до 2 МБ. */
export default function FileUpload({ number, has }: { number: number; has: boolean }) {
  const [state, action, pending] = useActionState(uploadRequestFileAction, undefined);
  const [tooBig, setTooBig] = useState(false);
  return (
    <form action={action} className="form" style={{ marginTop: 10 }}>
      <input type="hidden" name="number" value={number} />
      <div className="field">
        <label htmlFor="req-file">{has ? "Заменить файл" : "Прикрепить файл"}</label>
        <input id="req-file" name="file" type="file" className="input" accept="application/pdf,image/jpeg,image/png" required
          onChange={(e) => setTooBig((e.target.files?.[0]?.size ?? 0) > MAX)} />
        <div className="t2">PDF, JPG или PNG до 2 МБ. Файл увидят только вы и учебный офис.</div>
      </div>
      {tooBig && <div className="err-banner" role="alert">Файл больше 2 МБ. Сожмите его или сфотографируйте заново.</div>}
      {state?.error && !tooBig && <div className="err-banner" role="alert">{state.error}</div>}
      {state?.ok && <div className="ok-banner" role="status">{state.ok}</div>}
      <button className="btn sm secondary" disabled={pending || tooBig}>{pending ? "Загружаем…" : "Загрузить"}</button>
    </form>
  );
}
