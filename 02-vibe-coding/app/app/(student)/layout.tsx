import AutoRefresh from "@/components/AutoRefresh";
import TabBar from "@/components/TabBar";
import { requireStudent } from "@/lib/auth";

export default async function StudentLayout({ children }: { children: React.ReactNode }) {
  await requireStudent();
  return (
    <>
      <main className="page">{children}</main>
      <TabBar />
      <AutoRefresh />
    </>
  );
}
