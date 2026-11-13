import Link from "next/link";
export default function NotFound() {
  return (
    <main className="page" style={{ paddingTop: 60 }}>
      <div className="card empty">
        <div className="t1" style={{ fontSize: 20 }}>Страница не найдена</div>
        <div className="t2">Возможно, ссылка устарела или у вас нет к ней доступа.</div>
        <Link href="/" className="btn" style={{ marginTop: 14 }}>На главную</Link>
      </div>
    </main>
  );
}
