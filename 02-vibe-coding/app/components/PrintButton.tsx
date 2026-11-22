"use client";
export default function PrintButton() {
  return <button type="button" className="pillbtn glass" onClick={() => window.print()}>Сохранить PDF</button>;
}
