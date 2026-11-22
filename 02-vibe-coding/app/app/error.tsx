"use client";
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="page" style={{ paddingTop: 60 }}>
      <div className="card empty">
        <div className="t1" style={{ fontSize: 20 }}>Что-то пошло не так</div>
        <div className="t2">Мы уже знаем об ошибке. Попробуйте ещё раз.</div>
        <button className="btn" style={{ marginTop: 14 }} onClick={reset}>Повторить</button>
      </div>
    </main>
  );
}
