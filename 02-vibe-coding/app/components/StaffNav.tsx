"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/staff", label: "Заявки" },
  { href: "/staff/schedule", label: "Расписание" },
  { href: "/staff/announce", label: "Объявление" },
];

export default function StaffNav() {
  const p = usePathname();
  const active = (h: string) => (h === "/staff" ? p === "/staff" || p.startsWith("/staff/requests") : p.startsWith(h));
  return (
    <nav className="staff-nav" aria-label="Разделы">
      {ITEMS.map((i) => <Link key={i.href} href={i.href} aria-current={active(i.href) ? "page" : undefined}>{i.label}</Link>)}
    </nav>
  );
}
