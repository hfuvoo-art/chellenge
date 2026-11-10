// Каталог справок и заявлений. Один источник для формы, помощника и кабинета сотрудника.

export type Field =
  | { name: string; label: string; kind: "select"; options: string[] }
  | { name: string; label: string; kind: "text"; placeholder?: string; optional?: boolean }
  | { name: string; label: string; kind: "textarea"; placeholder?: string; optional?: boolean }
  | { name: string; label: string; kind: "number"; min: number; max: number }
  | { name: string; label: string; kind: "subject" };

export type RequestType = {
  type: string;
  title: string;
  group: "cert" | "statement";
  description: string;
  eta: string;
  fields: Field[];
};

export const REQUEST_TYPES: RequestType[] = [
  {
    type: "cert_study", title: "Справка об обучении", group: "cert",
    description: "Подтверждает, что вы студент. Электронная версия с QR-кодом проверки.", eta: "1 рабочий день",
    fields: [
      { name: "place", label: "Куда", kind: "select", options: ["По месту требования", "Работодателю", "В посольство", "В банк"] },
      { name: "format", label: "Формат", kind: "select", options: ["Электронная (PDF с QR-кодом)", "Бумажная"] },
      { name: "copies", label: "Экземпляров", kind: "number", min: 1, max: 5 },
    ],
  },
  {
    type: "cert_military", title: "Справка для военкомата", group: "cert",
    description: "Форма для военного комиссариата. Только бумажная, с печатью.", eta: "2 рабочих дня",
    fields: [
      { name: "place", label: "Военкомат", kind: "text", placeholder: "Например, ОВК Центрального района" },
      { name: "copies", label: "Экземпляров", kind: "number", min: 1, max: 3 },
    ],
  },
  {
    type: "cert_scholarship", title: "Справка о стипендии", group: "cert",
    description: "Размер стипендии за выбранный период.", eta: "2 рабочих дня",
    fields: [
      { name: "period", label: "Период", kind: "select", options: ["Последние 3 месяца", "Последние 6 месяцев", "Текущий год"] },
      { name: "format", label: "Формат", kind: "select", options: ["Электронная (PDF с QR-кодом)", "Бумажная"] },
    ],
  },
  {
    type: "retake", title: "Заявление на пересдачу", group: "statement",
    description: "Пересдача экзамена или зачёта. По болезни приложите справку.", eta: "до 3 рабочих дней",
    fields: [
      { name: "subject", label: "Дисциплина", kind: "subject" },
      { name: "reason", label: "Причина", kind: "select", options: ["Болезнь (есть справка)", "Академическая задолженность", "Семейные обстоятельства", "Другое"] },
      { name: "comment", label: "Комментарий", kind: "textarea", placeholder: "Например, номер медицинской справки", optional: true },
    ],
  },
  {
    type: "individual_plan", title: "Заявление на индивидуальный график", group: "statement",
    description: "Свободное посещение на время работы, спорта или лечения.", eta: "до 5 рабочих дней",
    fields: [
      { name: "reason", label: "Основание", kind: "select", options: ["Работа по профилю", "Спортивные сборы", "Лечение", "Другое"] },
      { name: "period", label: "Период", kind: "text", placeholder: "Например, 15.11–20.12" },
      { name: "comment", label: "Комментарий", kind: "textarea", optional: true },
    ],
  },
  {
    type: "academic_leave", title: "Заявление на академический отпуск", group: "statement",
    description: "Перерыв в учёбе до 2 лет по медицинским, семейным или иным причинам.", eta: "до 10 рабочих дней",
    fields: [
      { name: "reason", label: "Основание", kind: "select", options: ["Медицинские показания", "Семейные обстоятельства", "Призыв на военную службу", "Другое"] },
      { name: "from", label: "С какой даты", kind: "text", placeholder: "ДД.ММ.ГГГГ" },
      { name: "comment", label: "Комментарий", kind: "textarea", optional: true },
    ],
  },
];

export function requestType(type: string): RequestType | undefined {
  return REQUEST_TYPES.find((t) => t.type === type);
}

export const STATUS_LABEL: Record<string, string> = {
  submitted: "Подана",
  in_progress: "В работе",
  ready: "Готово",
  rejected: "Отклонена",
};
