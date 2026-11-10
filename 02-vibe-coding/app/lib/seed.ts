import type Database from "better-sqlite3";
import bcrypt from "bcryptjs";
import crypto from "node:crypto";
import { roomLabel } from "./format";
import { addDays, mondayOf, todayMsk, weekday } from "./time";

// Все данные вымышленные. Совпадения с реальными людьми случайны.
// Расписание строится вокруг текущей даты, чтобы на главной всегда были пары и изменения.

type Slot = [day: number, start: string, end: string, subject: string, kind: string, room: string, teacher: string];

const P = {
  1: ["09:00", "10:30"],
  2: ["10:40", "12:10"],
  3: ["12:40", "14:10"],
  4: ["14:20", "15:50"],
  5: ["16:00", "17:30"],
} as const;

function s(day: number, pair: 1 | 2 | 3 | 4 | 5, subject: string, kind: string, room: string, teacher: string): Slot {
  return [day, P[pair][0], P[pair][1], subject, kind, room, teacher];
}

const MO = "МО-2-04";
const EK = "ЭК-4-01";

const TEMPLATES: Record<string, Slot[]> = {
  [MO]: [
    s(0, 1, "Теория международных отношений", "Лекция", "301", "проф. Галкина Е. А."),
    s(0, 2, "Английский язык", "Практика", "118", "Петрова А. С."),
    s(0, 3, "История дипломатии", "Семинар", "224", "доц. Лебедев К. П."),
    s(1, 2, "Мировая экономика", "Семинар", "214", "доц. Морозов И. В."),
    s(1, 3, "Английский язык", "Практика", "118", "Петрова А. С."),
    s(1, 4, "Теория международных отношений", "Лекция", "301", "проф. Галкина Е. А."),
    s(2, 1, "Международное право", "Лекция", "Актовый зал", "доц. Ершова М. Н."),
    s(2, 2, "Международное право", "Практика", "312", "Сафонов Д. А."),
    s(2, 3, "Второй иностранный (французский)", "Практика", "120", "Леруа Н. Ж."),
    s(3, 2, "Мировая экономика", "Лекция", "Актовый зал", "доц. Морозов И. В."),
    s(3, 3, "История дипломатии", "Лекция", "224", "доц. Лебедев К. П."),
    s(3, 4, "Физическая культура", "Практика", "Спортзал", "Котов А. В."),
    s(4, 1, "Второй иностранный (французский)", "Практика", "120", "Леруа Н. Ж."),
    s(4, 2, "Английский язык", "Практика", "118", "Петрова А. С."),
    s(4, 3, "Международное право", "Семинар", "312", "Сафонов Д. А."),
    s(5, 2, "Теория международных отношений", "Семинар", "305", "Орлов В. Д."),
  ],
  [EK]: [
    s(0, 2, "Эконометрика", "Лекция", "410", "проф. Зимин С. Л."),
    s(0, 3, "Эконометрика", "Практика", "Комп. класс 2", "Яковлева О. И."),
    s(1, 1, "Корпоративные финансы", "Лекция", "402", "доц. Руденко П. А."),
    s(1, 2, "Маркетинг", "Семинар", "407", "Краснова Л. В."),
    s(2, 3, "Научный семинар по ВКР", "Семинар", "415", "проф. Зимин С. Л."),
    s(3, 2, "Корпоративные финансы", "Семинар", "402", "доц. Руденко П. А."),
    s(3, 3, "Эконометрика", "Практика", "Комп. класс 2", "Яковлева О. И."),
    s(4, 1, "Маркетинг", "Лекция", "Актовый зал", "Краснова Л. В."),
    s(4, 2, "Деловой английский", "Практика", "118", "Фомина Т. Р."),
  ],
};

const ROOM_SWAP: Record<string, string> = {
  "214": "405", "118": "122", "301": "Актовый зал", "224": "230", "312": "318", "120": "126",
  "410": "411", "402": "404", "407": "Комп. класс 1", "415": "417", "305": "309",
};

export function seed(db: Database.Database, now = new Date()): void {
  const today = todayMsk(now);
  const iso = (date: string, time = "10:00") => new Date(`${date}T${time}:00+03:00`).toISOString();
  const hash = (p: string) => bcrypt.hashSync(p, 10);

  const tx = db.transaction(() => {
    // Аккаунты создаются один раз и потом только обновляются: так сброс демо не разрывает открытые сессии.
    const upsert = db.prepare(`INSERT INTO users (login,password_hash,role,last_name,first_name,middle_name,faculty,program,course,group_name,student_card,email,position,gender)
      VALUES (@login,@password_hash,@role,@last_name,@first_name,@middle_name,@faculty,@program,@course,@group_name,@student_card,@email,@position,@gender)
      ON CONFLICT(login) DO UPDATE SET role=excluded.role,last_name=excluded.last_name,first_name=excluded.first_name,middle_name=excluded.middle_name,
        faculty=excluded.faculty,program=excluded.program,course=excluded.course,group_name=excluded.group_name,student_card=excluded.student_card,
        email=excluded.email,position=excluded.position,gender=excluded.gender`);
    const exists = db.prepare("SELECT id FROM users WHERE login = ?");
    const addUser = (u: Record<string, string | number | null> & { login: string; password: string }): number => {
      const { password, ...rest } = u;
      const found = exists.get(u.login) as { id: number } | undefined;
      upsert.run({ ...rest, password_hash: found ? "" : hash(password) });
      // Пароль существующего аккаунта не трогаем (ON CONFLICT его не обновляет).
      return (exists.get(u.login) as { id: number }).id;
    };

    const alina = addUser({
      login: "alina", password: "demo2026", role: "student", gender: "f",
      last_name: "Соколова", first_name: "Алина", middle_name: "Игоревна",
      faculty: "Факультет международных отношений", program: "Международные отношения",
      course: 2, group_name: MO, student_card: "24-0417", email: "alina.sokolova@student.example", position: null,
    });

    const timur = addUser({
      login: "timur", password: "demo2026", role: "student", gender: "m",
      last_name: "Ахмедов", first_name: "Тимур", middle_name: "Русланович",
      faculty: "Факультет экономики и бизнеса", program: "Экономика",
      course: 4, group_name: EK, student_card: "22-1183", email: "timur.akhmedov@student.example", position: null,
    });

    addUser({
      login: "dekanat", password: "staff2026", role: "staff", gender: "f",
      last_name: "Белова", first_name: "Ирина", middle_name: "Павловна",
      faculty: "Учебный офис", program: "", course: null, group_name: null, student_card: null,
      email: "dekanat@uni.example", position: "Специалист учебного офиса",
    });

    // Расписание: от двух недель назад до конца семестра.
    const addClass = db.prepare(`INSERT INTO schedule (group_name,date,start,end,subject,kind,room,teacher,status,old_room,note)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)`);
    const from = addDays(mondayOf(today), -14);
    const to = addDays(today, 45);
    let dayIndex = 0;
    for (let d = from; d <= to; d = addDays(d, 1)) {
      const wd = weekday(d);
      if (wd === 6) continue;
      dayIndex++;
      // Разовые изменения ставим только в окне «вчера … +5 дней»: один день недели попадает в окно один раз,
      // поэтому перенос не повторяется из недели в неделю.
      const near = d >= addDays(today, -1) && d <= addDays(today, 5);
      for (const group of [MO, EK]) {
        const slots = TEMPLATES[group].filter((x) => x[0] === wd);
        slots.forEach((x, i) => {
          let status = "ok";
          let room = x[5];
          let oldRoom: string | null = null;
          let note: string | null = null;
          if (near && i === 0 && dayIndex % 2 === 0 && ROOM_SWAP[room]) {
            status = "moved"; oldRoom = room; room = ROOM_SWAP[room]; note = "Аудитория изменена";
          }
          if (near && slots.length > 2 && i === slots.length - 1 && dayIndex % 3 === 0) {
            status = "cancelled"; note = "Преподаватель на конференции, пара перенесена на резервный день";
          }
          // Сегодня у первой группы всегда есть смена аудитории — чтобы на демо было видно изменения.
          if (d === today && group === MO && (x[3] === "Мировая экономика" || i === 0) && status === "ok") {
            status = "moved"; oldRoom = x[5]; room = ROOM_SWAP[x[5]] ?? "405"; note = "Аудитория изменена";
          }
          addClass.run(group, d, x[1], x[2], x[3], x[4], room, x[6], status, oldRoom, note);
        });
      }
    }

    // Успеваемость
    const addSubject = db.prepare(`INSERT INTO subjects (student_id,semester,name,control,teacher,points,final,blocker,exam_date) VALUES (?,?,?,?,?,?,?,?,?)`);
    const addWork = db.prepare(`INSERT INTO works (subject_id,date,title,points,max_points,done) VALUES (?,?,?,?,?,?)`);
    const examStart = "2026-12-21";

    type Sub = { name: string; control: "exam" | "credit" | "diff"; teacher: string; points: number; blocker?: string; exam?: string; works: [number, string, number | null, number][] };
    const current = (sid: number, semester: number, list: Sub[]) => {
      for (const x of list) {
        const id = Number(addSubject.run(sid, semester, x.name, x.control, x.teacher, x.points, null, x.blocker ?? null, x.exam ?? null).lastInsertRowid);
        for (const [offset, title, pts, max] of x.works) {
          const date = addDays(today, offset);
          addWork.run(id, date, title, pts, max, pts === null ? 0 : 1);
        }
      }
    };
    const past = (sid: number, semester: number, list: [string, "exam" | "credit" | "diff", string][]) => {
      for (const [name, control, final] of list) addSubject.run(sid, semester, name, control, "—", final === "зачёт" ? 70 : final === "5" ? 90 : final === "4" ? 78 : 62, final, null, null);
    };

    current(alina, 3, [
      { name: "Мировая экономика", control: "exam", teacher: "доц. Морозов И. В.", points: 88, exam: examStart, works: [[-40, "Контрольная 1", 18, 20], [-21, "Доклад", 28, 30], [-7, "Тест по модулю", 9, 10]] },
      { name: "Английский язык", control: "exam", teacher: "Петрова А. С.", points: 84, exam: "2026-12-24", works: [[-35, "Эссе", 17, 20], [-14, "Аудирование", 18, 20]] },
      { name: "Теория международных отношений", control: "exam", teacher: "проф. Галкина Е. А.", points: 71, exam: "2026-12-27", works: [[-30, "Реферат", 21, 30], [-10, "Коллоквиум", 14, 20]] },
      { name: "Международное право", control: "credit", teacher: "Сафонов Д. А.", points: 38, blocker: "Не сданы 2 практические работы: без них нет допуска к зачёту", works: [[-28, "Практическая 1", 12, 15], [-12, "Практическая 2", null, 15], [-5, "Практическая 3", null, 15]] },
      { name: "История дипломатии", control: "credit", teacher: "доц. Лебедев К. П.", points: 92, works: [[-20, "Эссе", 28, 30]] },
      { name: "Второй иностранный (французский)", control: "diff", teacher: "Леруа Н. Ж.", points: 76, works: [[-25, "Диктант", 15, 20]] },
      { name: "Физическая культура", control: "credit", teacher: "Котов А. В.", points: 64, works: [[-9, "Нормативы", 20, 30]] },
    ]);
    past(alina, 1, [["Введение в теорию МО", "exam", "5"], ["Английский язык", "exam", "5"], ["История России", "exam", "4"], ["Экономическая теория", "exam", "5"], ["Логика", "credit", "зачёт"]]);
    past(alina, 2, [["Английский язык", "exam", "5"], ["Политология", "exam", "4"], ["Мировая политика", "exam", "5"], ["Математика для гуманитариев", "credit", "зачёт"]]);

    current(timur, 7, [
      { name: "Эконометрика", control: "exam", teacher: "проф. Зимин С. Л.", points: 52, blocker: "Мало баллов для допуска: нужно ещё 3 балла (порог 55)", exam: examStart, works: [[-30, "Домашнее задание 1", 11, 20], [-14, "Контрольная", 9, 20], [-3, "Проект", null, 20]] },
      { name: "Корпоративные финансы", control: "exam", teacher: "доц. Руденко П. А.", points: 79, exam: "2026-12-25", works: [[-21, "Кейс", 24, 30]] },
      { name: "Маркетинг", control: "diff", teacher: "Краснова Л. В.", points: 90, works: [[-18, "Проект", 27, 30]] },
      { name: "Деловой английский", control: "credit", teacher: "Фомина Т. Р.", points: 81, works: [[-11, "Презентация", 17, 20]] },
      { name: "Научный семинар по ВКР", control: "credit", teacher: "проф. Зимин С. Л.", points: 60, works: [[-6, "Глава 1 ВКР", 15, 20]] },
    ]);
    past(timur, 6, [["Статистика", "exam", "долг"], ["Микроэкономика 2", "exam", "4"], ["Финансовые рынки", "exam", "4"], ["Бухучёт", "credit", "зачёт"]]);
    past(timur, 5, [["Макроэкономика 2", "exam", "4"], ["Теория игр", "exam", "3"], ["Английский язык", "exam", "5"]]);

    // Дедлайны
    const addDeadline = db.prepare(`INSERT INTO deadlines (student_id,title,subject,due_at) VALUES (?,?,?,?)`);
    addDeadline.run(alina, "Эссе по истории дипломатии", "История дипломатии", iso(addDays(today, 2), "23:59"));
    addDeadline.run(alina, "Практические 2 и 3 по праву", "Международное право", iso(addDays(today, 6), "18:00"));
    addDeadline.run(alina, "Доклад по теории МО", "Теория международных отношений", iso(addDays(today, 9), "12:00"));
    addDeadline.run(timur, "Проект по эконометрике", "Эконометрика", iso(addDays(today, 3), "23:59"));
    addDeadline.run(timur, "Глава 2 ВКР научному руководителю", "Научный семинар по ВКР", iso(addDays(today, 12), "18:00"));
    addDeadline.run(timur, "Пересдача: Статистика", "Статистика", iso(addDays(today, 15), "10:40"));

    // Заявки
    const addReq = db.prepare(`INSERT INTO requests (number,student_id,type,title,details,status,staff_comment,verify_code,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)`);
    const addEvent = db.prepare(`INSERT INTO request_events (request_id,status,comment,actor,created_at) VALUES (?,?,?,?,?)`);
    const code = () => crypto.randomBytes(6).toString("hex").toUpperCase();
    const mkReq = (number: number, sid: number, type: string, title: string, details: object, events: [string, string | null, string, string][], verify = false) => {
      const last = events[events.length - 1];
      const id = Number(addReq.run(number, sid, type, title, JSON.stringify(details), last[0], last[0] === "ready" || last[0] === "rejected" ? last[1] : null, verify ? code() : null, events[0][3], last[3]).lastInsertRowid);
      for (const [st, cm, actor, at] of events) addEvent.run(id, st, cm, actor, at);
      return id;
    };
    mkReq(1027, timur, "retake", "Заявление на пересдачу", { subject: "Статистика", reason: "Академическая задолженность", preferred: "Любая дата" },
      [["submitted", null, "Студент", iso(addDays(today, -12), "11:20")], ["in_progress", null, "Учебный офис", iso(addDays(today, -11), "09:40")], ["ready", `Пересдача назначена на ${addDays(today, 15).split("-").reverse().join(".")}, 10:40, ауд. 410`, "Учебный офис", iso(addDays(today, -10), "15:05")]]);
    mkReq(1031, timur, "cert_military", "Справка для военкомата", { place: "Военный комиссариат", copies: 1, format: "Бумажная" },
      [["submitted", null, "Студент", iso(addDays(today, -2), "18:12")], ["in_progress", null, "Учебный офис", iso(addDays(today, -1), "10:02")]]);
    mkReq(1038, alina, "cert_study", "Справка об обучении", { place: "По месту требования", copies: 1, format: "Электронная (PDF с QR-кодом)" },
      [["submitted", null, "Студент", iso(addDays(today, -1), "20:41")], ["in_progress", null, "Учебный офис", iso(today, "09:05")], ["ready", "Справка готова. Откройте её по кнопке ниже: внутри QR-код для проверки, файл можно сохранить как PDF.", "Учебный офис", iso(today, "09:30")]], true);
    // Переписка по заявке: один вопрос с ответом и один вопрос, который ждёт ответа офиса.
    const addMsg = db.prepare("INSERT INTO request_messages (request_id,author,author_name,text,created_at) VALUES (?,?,?,?,?)");
    const idOf = (n: number) => (db.prepare("SELECT id FROM requests WHERE number = ?").get(n) as { id: number }).id;
    addMsg.run(idOf(1027), "student", "Тимур А.", "Здравствуйте! Можно ли перенести пересдачу на неделю раньше?", iso(addDays(today, -10), "16:20"));
    addMsg.run(idOf(1027), "staff", "Ирина Б., учебный офис", "Добрый день! Раньше нельзя: комиссия собирается один раз. Дата в заявке окончательная.", iso(addDays(today, -9), "10:15"));
    addMsg.run(idOf(1031), "student", "Тимур А.", "Здравствуйте! Справку можно будет забрать в пятницу после 16:00?", iso(addDays(today, -1), "12:30"));

    // Одна новая заявка, чтобы очередь учебного офиса не была пустой при первом входе.
    mkReq(1041, timur, "cert_study", "Справка об обучении", { place: "Работодателю", copies: 2, format: "Бумажная" },
      [["submitted", null, "Студент", iso(addDays(today, -1), "21:15")]]);

    // Уведомления
    const addN = db.prepare(`INSERT INTO notifications (user_id,kind,title,body,link,created_at,read_at) VALUES (?,?,?,?,?,?,?)`);
    const ann = [
      ["Продлён приём заявлений на повышенную стипендию", "Заявления принимаются до 20 ноября включительно. Нажмите, чтобы подать заявление онлайн.", -1, "16:30"],
      ["Ярмарка стажировок 14 ноября", "Партнёры факультетов проведут собеседования в холле главного корпуса с 12:00 до 17:00.", -3, "12:00"],
    ] as const;
    for (const uid of [alina, timur]) {
      for (const [t, b, off, time] of ann) addN.run(uid, "announcement", t, b, t.includes("стипенди") ? "/requests/new?type=scholarship_plus" : null, iso(addDays(today, off), time), off < -2 ? iso(addDays(today, off), "18:00") : null);
    }
    const movedToday = db.prepare("SELECT subject, room, old_room, start FROM schedule WHERE group_name = ? AND date = ? AND status = 'moved' ORDER BY start LIMIT 1").get(MO, today) as
      | { subject: string; room: string; old_room: string; start: string } | undefined;
    if (movedToday) addN.run(alina, "schedule", `${movedToday.subject}: новая аудитория`, `Сегодня в ${movedToday.start}: ${roomLabel(movedToday.room)} вместо ${roomLabel(movedToday.old_room)}.`, "/schedule", iso(today, "08:10"), null);
    addN.run(alina, "request", "Справка об обучении готова", "Заявка № 1038: откройте справку с QR-кодом.", "/requests/1038", iso(today, "09:30"), null);
    addN.run(alina, "deadline", "Через 2 дня: эссе по истории дипломатии", "Сдать до 23:59 в системе курса.", "/study", iso(today, "07:00"), null);
    addN.run(timur, "request", "Справка для военкомата в работе", "Заявка № 1031 принята учебным офисом.", "/requests/1031", iso(addDays(today, -1), "10:02"), null);
    addN.run(timur, "deadline", "Риск недопуска: эконометрика", "Не хватает 3 баллов до допуска. Сдайте проект до дедлайна.", "/study", iso(today, "07:00"), null);
  });
  tx();
}
