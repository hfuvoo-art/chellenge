import { getDb } from "@/lib/db";
import { humanDate, todayMsk } from "@/lib/time";

export const dynamic = "force-dynamic";

// Публичная проверка справки по QR-коду. Показывает минимум данных: номер, тип, дату и маску ФИО.
export default async function VerifyPage({ params }: { params: Promise<{ code: string }> }) {
  const code = (await params).code.toUpperCase();
  const row = /^[0-9A-F]{12}$/.test(code)
    ? (getDb().prepare("SELECT r.number, r.title, r.updated_at, u.last_name, u.first_name, u.middle_name FROM requests r JOIN users u ON u.id = r.student_id WHERE r.verify_code = ? AND r.status = 'ready'").get(code) as
        | { number: number; title: string; updated_at: string; last_name: string; first_name: string; middle_name: string } | undefined)
    : undefined;
  return (
    <main className="page" style={{ paddingTop: 48 }}>
      <h1 className="large">Проверка справки</h1>
      {row ? (
        <div className="card">
          <div className="ok-banner">Справка действительна</div>
          <div className="kv" style={{ marginTop: 8 }}><span>Документ</span><span>{row.title} № {row.number}</span></div>
          <div className="kv"><span>Выдана</span><span>{humanDate(todayMsk(new Date(row.updated_at)), false)}</span></div>
          <div className="kv"><span>Студент</span><span>{row.last_name[0]}*** {row.first_name[0]}. {row.middle_name[0]}.</span></div>
        </div>
      ) : (
        <div className="card"><div className="err-banner">Справка не найдена или отозвана</div></div>
      )}
      <p className="concept">Концепт для конкурса. Не официальный сервис, данные вымышленные.</p>
    </main>
  );
}
