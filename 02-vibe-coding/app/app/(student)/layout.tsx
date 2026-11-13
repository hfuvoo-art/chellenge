import AutoRefresh from "@/components/AutoRefresh";
import GlassLight from "@/components/GlassLight";
import TabBar from "@/components/TabBar";
import { requireStudent } from "@/lib/auth";

export default async function StudentLayout({ children }: { children: React.ReactNode }) {
  const u = await requireStudent();
  return (
    <>
      <TabBar name={`${u.first_name} ${u.last_name}`} sub={`Группа ${u.group_name ?? ""}`} initials={`${u.first_name[0]}${u.last_name[0]}`} />
      <main className="page shell">{children}</main>
      <AutoRefresh />
      <GlassLight />
    </>
  );
}
