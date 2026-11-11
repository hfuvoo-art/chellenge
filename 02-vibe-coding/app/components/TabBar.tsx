"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconCalendar, IconChart, IconDoc, IconHome, IconMegaphone, IconSpark } from "./icons";

const ICONS = { home: IconHome, calendar: IconCalendar, chart: IconChart, doc: IconDoc, megaphone: IconMegaphone };

/** Пункт меню. Иконка задаётся именем: серверный layout не может передать сюда сам компонент.
 *  exact: пункт активен только на своём адресе; also: дополнительные адреса, где он тоже активен. */
export type TabItem = { href: string; label: string; icon: keyof typeof ICONS; exact?: boolean; also?: string[] };

const STUDENT_TABS: TabItem[] = [
  { href: "/", label: "Сегодня", icon: "home", exact: true },
  { href: "/schedule", label: "Расписание", icon: "calendar" },
  { href: "/study", label: "Учёба", icon: "chart" },
  { href: "/requests", label: "Заявки", icon: "doc" },
];

type Props = {
  name: string;
  sub: string;
  initials: string;
  /** Свой список пунктов (кабинет сотрудника). По умолчанию пункты студента. */
  items?: TabItem[];
  /** Показывать кнопку «Помощник». */
  assistant?: boolean;
  /** Подпись под названием в боковом меню. */
  brandSub?: string;
  /** Куда ведёт карточка пользователя; null: карточка без ссылки. */
  userHref?: string | null;
};

/** Навигация: на телефоне плавающая панель снизу, на компьютере (от 1024 px) боковое меню.
 *  Стеклянный индикатор переезжает к активному разделу (позиция задаётся переменной --i, число пунктов --n). */
export default function TabBar({ name, sub, initials, items = STUDENT_TABS, assistant = true, brandSub = "Деканат, который отвечает", userHref = "/profile" }: Props) {
  const path = usePathname();
  const under = (href: string) => path === href || path.startsWith(href + "/");
  const active = (t: TabItem) => (t.exact ? path === t.href : under(t.href)) || !!t.also?.some(under);
  const index = items.findIndex(active);
  const user = (
    <>
      <span className="ava" aria-hidden>{initials}</span>
      <span><b>{name}</b><small>{sub}</small></span>
    </>
  );
  return (
    <nav className="tabwrap" aria-label="Основное меню">
      <div className="tabinner">
        <Link href={items[0].href} className="side-brand desk-only">
          <span className="logo" aria-hidden>Д</span>
          <span><b>Мой деканат</b><small>{brandSub}</small></span>
        </Link>
        <div className="tabbar glass" style={{ "--i": index, "--n": items.length } as React.CSSProperties} data-none={index < 0 || undefined}>
          <span className="tab-ind" aria-hidden />
          {items.map((t) => {
            const Icon = ICONS[t.icon];
            const on = active(t);
            return (
              <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined}>
                <Icon filled={on} />
                <span>{t.label}</span>
              </Link>
            );
          })}
        </div>
        {assistant && (
          <Link href="/assistant" className="fab glass" aria-label="Помощник деканата" aria-current={under("/assistant") ? "page" : undefined}>
            <IconSpark />
            <span className="fab-label desk-only">Помощник</span>
          </Link>
        )}
        {userHref ? (
          <Link href={userHref} className="side-user desk-only" aria-current={under(userHref) ? "page" : undefined}>{user}</Link>
        ) : (
          <div className="side-user desk-only">{user}</div>
        )}
      </div>
    </nav>
  );
}
