import { currentUser } from "@/lib/auth";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

/** Отдаёт файл заявки. Студент получает только файл своей заявки, сотрудник — любой. Остальным 404. */
export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const user = await currentUser();
  const id = Number((await params).id);
  if (!user || !Number.isInteger(id)) return new Response("Не найдено", { status: 404 });
  const row = getDb().prepare(
    "SELECT f.name, f.mime, f.data, r.student_id FROM request_files f JOIN requests r ON r.id = f.request_id WHERE f.request_id = ?",
  ).get(id) as { name: string; mime: string; data: Buffer; student_id: number } | undefined;
  if (!row || (user.role !== "staff" && row.student_id !== user.id)) return new Response("Не найдено", { status: 404 });
  return new Response(new Uint8Array(row.data), {
    headers: {
      "Content-Type": row.mime,
      // Файл всегда скачивается, а не открывается внутри сайта: так вложенный в него код не выполнится на нашем адресе.
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(row.name)}`,
      "Content-Security-Policy": "default-src 'none'; sandbox",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "private, no-store",
    },
  });
}
