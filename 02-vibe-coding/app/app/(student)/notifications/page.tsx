import Link from "next/link";
import { markAllReadAction } from "@/app/actions";
import { IconBack, IconBell, IconCalendar, IconChat, IconClock, IconDoc } from "@/components/icons";
import { requireStudent } from "@/lib/auth";
import { notificationsOf } from "@/lib/data";
import { relativeTime } from "@/lib/time";

export const dynamic = "force-dynamic";
const KIND = {
  schedule: { label: "Расписание", Icon: IconCalendar, bg: "var(--warn-bg)", fg: "var(--warn)" },
  request: { label: "Заявка", Icon: IconDoc, bg: "var(--ok-soft)", fg: "var(--ok)" },
  deadline: { label: "Дедлайн", Icon: IconClock, bg: "var(--bad-soft)", fg: "var(--bad)" },
  announcement: { label: "Объявление", Icon: IconChat, bg: "var(--brand-soft)", fg: "var(--brand)" },
} as const;

export default async function NotificationsPage({ searchParams }: { searchParams: Promise<{ f?: string }> }) {
  const user = await requireStudent();
  const f = (await searchParams).f;
  const all = notificationsOf(user.id);
  const list = f && f in KIND ? all.filter((n) => n.kind === f) : all;
  const unread = all.filter((n) => !n.read_at).length;
  return (
    <>
      <div className="topbar" style={{ justifyContent: "space-between" }}>
        <Link href="/" className="pillbtn glass"><IconBack /> Сегодня</Link>
        {unread > 0 && <form action={markAllReadAction}><button className="pillbtn glass">Прочитать все</button></form>}
      </div>
      <h1 className="large">Уведомления</h1>
      <div className="chips" style={{ padding: "0 2px 10px" }}>
        <Link href="/notifications" className="chip" aria-current={!f ? "page" : undefined} style={!f ? { borderColor: "var(--brand)", color: "var(--brand)" } : undefined}>Все</Link>
        {Object.entries(KIND).map(([k, v]) => (
          <Link key={k} href={`/notifications?f=${k}`} className="chip" aria-current={f === k ? "page" : undefined} style={f === k ? { borderColor: "var(--brand)", color: "var(--brand)" } : undefined}>{v.label}</Link>
        ))}
      </div>
      {list.length ? (
        <div className="card list">
          {list.map((n) => {
            const k = KIND[n.kind as keyof typeof KIND] ?? KIND.announcement;
            const inner = (
              <>
                <div className="ic" style={{ background: k.bg, color: k.fg }}><k.Icon /></div>
                <div className="g">
                  <div className="t1">{!n.read_at && <span className="sr">Новое: </span>}{n.title}</div>
                  <div className="t2">{n.body}</div>
                  <div className="t2" style={{ fontSize: 12.5 }}>{k.label} · {relativeTime(n.created_at)}</div>
                </div>
                {!n.read_at && <span className="dotc" style={{ background: "var(--brand)" }} aria-hidden />}
              </>
            );
            return n.link ? <Link key={n.id} href={n.link} className="cell">{inner}</Link> : <div key={n.id} className="cell">{inner}</div>;
          })}
        </div>
      ) : (
        <div className="card empty"><div className="ill"><IconBell /></div><div className="t1">Здесь пусто</div><div className="t2">Новые объявления и изменения появятся здесь</div></div>
      )}
    </>
  );
}
