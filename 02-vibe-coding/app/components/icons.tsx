// Иконки нарисованы для проекта вручную (SVG), без сторонних наборов.
type P = { filled?: boolean; size?: number; color?: string };

const stroke = (p: P) => ({ fill: "none", stroke: p.color ?? "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const });

export const IconHome = (p: P) =>
  p.filled ? (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 3 2.5 11h2.5v9h5.5v-6h3v6H19v-9h2.5z" /></svg>
  ) : (
    <svg viewBox="0 0 24 24" {...stroke(p)} aria-hidden><path d="M12 3.5 3.5 11v9h6v-6h5v6h6v-9z" /></svg>
  );
export const IconCalendar = (p: P) => (
  <svg viewBox="0 0 24 24" {...stroke(p)} fill={p.filled ? "currentColor" : "none"} aria-hidden>
    <rect x="3.5" y="5" width="17" height="15.5" rx="3" fillOpacity={p.filled ? 0.15 : 0} />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
  </svg>
);
export const IconChart = (p: P) => (
  <svg viewBox="0 0 24 24" fill={p.filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={p.filled ? 0 : 2} aria-hidden>
    <rect x="4" y="12" width="3.5" height="8" rx="1" /><rect x="10.25" y="6" width="3.5" height="14" rx="1" /><rect x="16.5" y="9" width="3.5" height="11" rx="1" />
  </svg>
);
export const IconDoc = (p: P) => (
  <svg viewBox="0 0 24 24" {...stroke(p)} fill={p.filled ? "currentColor" : "none"} aria-hidden>
    <path d="M7 3.5h7l5 5v12H7a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2z" fillOpacity={p.filled ? 0.15 : 0} /><path d="M14 3.5v5h5M9 13h6M9 16.5h4" />
  </svg>
);
export const IconSpark = (p: P) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8zM19 14l.9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9z" /></svg>
);
export const IconBell = (p: P) => (
  <svg viewBox="0 0 24 24" {...stroke(p)} aria-hidden><path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20.5a2.2 2.2 0 0 0 4 0" /></svg>
);
export const IconWarn = ({ color = "#e08600" }: P) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill={color} aria-hidden><path d="M12 2 1 21h22L12 2zm1 15h-2v-2h2v2zm0-4h-2V9h2v4z" /></svg>
);
export const IconCheck = (p: P) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={p.color ?? "currentColor"} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
);
export const IconClock = (p: P) => (
  <svg viewBox="0 0 24 24" {...stroke(p)} aria-hidden><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></svg>
);
export const IconChat = (p: P) => (
  <svg viewBox="0 0 24 24" {...stroke(p)} aria-hidden><path d="M4 5h16v11H9l-5 4z" /></svg>
);
export const IconSend = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12h14M13 6l6 6-6 6" /></svg>
);
export const IconPlus = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden><path d="M12 5v14M5 12h14" /></svg>
);
export const IconBack = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M15 5l-7 7 7 7" /></svg>
);
export const IconUser = (p: P) => (
  <svg viewBox="0 0 24 24" {...stroke(p)} aria-hidden><circle cx="12" cy="8.5" r="4" /><path d="M4.5 20a7.5 7.5 0 0 1 15 0" /></svg>
);
