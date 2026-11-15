// Файлы к заявкам (например, медицинская справка). Правила безопасности:
// тип определяем по первым байтам файла, а не по названию; размер ограничен;
// файл лежит в базе, а не в папке сайта, и отдаётся только владельцу заявки и учебному офису.

export const MAX_FILE_BYTES = 2 * 1024 * 1024;
export const MAX_TOTAL_BYTES = 40 * 1024 * 1024; // общий предел демо, чтобы диск сервера нельзя было забить
export const FILE_TYPES = ["retake", "academic_leave", "individual_plan", "scholarship_plus"]; // заявления, к которым нужен документ

/** Тип файла по сигнатуре. Всё, что не PDF, JPEG или PNG, отклоняем. */
export function sniffType(bytes: Uint8Array): { mime: string; ext: string } | null {
  const starts = (sig: number[]) => sig.every((b, i) => bytes[i] === b);
  if (starts([0x25, 0x50, 0x44, 0x46, 0x2d])) return { mime: "application/pdf", ext: "pdf" };
  if (starts([0xff, 0xd8, 0xff])) return { mime: "image/jpeg", ext: "jpg" };
  if (starts([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) return { mime: "image/png", ext: "png" };
  return null;
}

/** Безопасное имя для показа и скачивания: без путей и служебных символов, расширение берём из настоящего типа. */
export function safeName(original: string, ext: string): string {
  const base = original.replace(/^.*[\\/]/, "").replace(/\.[^.]*$/, "").replace(/[^\p{L}\p{N} _-]+/gu, "").trim().slice(0, 60) || "spravka";
  return `${base}.${ext}`;
}

export function humanSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} МБ` : `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}
