import Link from "next/link";
import type { User } from "@/lib/auth";
import { unreadCount } from "@/lib/data";
import { IconBell } from "./icons";

export default function TopBar({ user, left }: { user: User; left?: React.ReactNode }) {
  const unread = unreadCount(user.id);
  return (
    <div className="topbar">
      <div>{left}</div>
      <div style={{ display: "flex", gap: 8 }}>
        <Link href="/notifications" className="iconbtn glass" aria-label={unread ? `Уведомления, новых: ${unread}` : "Уведомления"}>
          <IconBell />
          {unread > 0 && <span className="dot-badge">{unread}</span>}
        </Link>
        <Link href="/profile" className="iconbtn glass" aria-label="Профиль">
          {user.first_name[0]}{user.last_name[0]}
        </Link>
      </div>
    </div>
  );
}
