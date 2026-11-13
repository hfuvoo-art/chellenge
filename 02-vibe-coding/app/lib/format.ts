// Мелкие помощники для текста интерфейса.

/** «ауд. 214», но «Актовый зал» и «Спортзал» без «ауд.». */
export function roomLabel(room: string): string {
  return /^\d/.test(room) ? `ауд. ${room}` : room;
}

/** Данные преподавателей (вымышленные): почта и часы консультаций. */
export function teacherContact(teacher: string): { email: string; hours: string } {
  const last = teacher.replace(/^(проф\.|доц\.)\s*/, "").split(" ")[0] ?? "teacher";
  const map: Record<string, string> = { а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i", й: "y", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "kh", ц: "ts", ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya" };
  const latin = [...last.toLowerCase()].map((c) => map[c] ?? c).join("");
  const days = ["по понедельникам", "по вторникам", "по средам", "по четвергам", "по пятницам"];
  const n = [...last].reduce((a, c) => a + c.charCodeAt(0), 0);
  return { email: `${latin}@uni.example`, hours: `${days[n % 5]}, 16:00–17:30, ауд. ${200 + (n % 9) * 12 + 3}` };
}
