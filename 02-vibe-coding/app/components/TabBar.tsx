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

export default function TabBar() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <nav className="tabwrap" aria-label="Основное меню">
      <div className="tabinner">
        <div className="tabbar glass">
          {TABS.map(({ href, label, Icon }) => (
            <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}>
              <Icon filled={active(href)} />
              {label}
            </Link>
          ))}
        </div>
        <Link href="/assistant" className="fab glass" aria-label="Помощник деканата" aria-current={active("/assistant") ? "page" : undefined}>
          <IconSpark />
        </Link>
      </div>
    </nav>
  );
}
