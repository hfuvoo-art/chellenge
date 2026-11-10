"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconCalendar, IconChart, IconDoc, IconHome, IconSpark } from "./icons";

const TABS = [
  { href: "/", label: "Сегодня", Icon: IconHome },
  { href: "/schedule", label: "Расписание", Icon: IconCalendar },
  { href: "/study", label: "Учёба", Icon: IconChart },
  { href: "/requests", label: "Заявки", Icon: IconDoc },
];

/** Навигация: на телефоне плавающая панель снизу, на компьютере (от 1024 px) боковое меню.
 *  Стеклянный индикатор переезжает к активному разделу (позиция задаётся переменной --i). */
export default function TabBar({ name, sub, initials }: { name: string; sub: string; initials: string }) {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  const index = TABS.findIndex((t) => active(t.href));
  return (
    <nav className="tabwrap" aria-label="Основное меню">
      <div className="tabinner">
        <Link href="/" className="side-brand desk-only">
          <span className="logo" aria-hidden>Д</span>
          <span><b>Мой деканат</b><small>Деканат, который отвечает</small></span>
        </Link>
        <div className="tabbar glass" style={{ "--i": index } as React.CSSProperties} data-none={index < 0 || undefined}>
          <span className="tab-ind" aria-hidden />
          {TABS.map(({ href, label, Icon }) => (
            <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}>
              <Icon filled={active(href)} />
              <span>{label}</span>
            </Link>
          ))}
        </div>
        <Link href="/assistant" className="fab glass" aria-label="Помощник деканата" aria-current={active("/assistant") ? "page" : undefined}>
          <IconSpark />
          <span className="fab-label desk-only">Помощник</span>
        </Link>
        <Link href="/profile" className="side-user desk-only" aria-current={active("/profile") ? "page" : undefined}>
          <span className="ava" aria-hidden>{initials}</span>
          <span><b>{name}</b><small>{sub}</small></span>
        </Link>
      </div>
    </nav>
  );
}
