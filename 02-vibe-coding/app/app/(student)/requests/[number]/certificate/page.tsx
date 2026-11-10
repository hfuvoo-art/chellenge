import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import QRCode from "qrcode";
import { IconBack } from "@/components/icons";
import PrintButton from "@/components/PrintButton";
import { requireStudent } from "@/lib/auth";
import { requestOf } from "@/lib/data";
import { humanDate, todayMsk } from "@/lib/time";

export default async function CertificatePage({ params }: { params: Promise<{ number: string }> }) {
  const user = await requireStudent();
  const number = Number((await params).number);
  const r = Number.isInteger(number) ? requestOf(user.id, number) : null;
  if (!r || r.status !== "ready" || !r.verify_code) notFound();
  const h = await headers();
  const origin = `${h.get("x-forwarded-proto") ?? "http"}://${h.get("host")}`;
  const verifyUrl = `${origin}/verify/${r.verify_code}`;
  const qr = await QRCode.toDataURL(verifyUrl, { margin: 1, width: 220, color: { dark: "#10131a" } });
  const issued = todayMsk(new Date(r.updated_at));
  return (
    <>
      <div className="topbar no-print" style={{ justifyContent: "space-between" }}>
        <Link href={`/requests/${r.number}`} className="pillbtn glass"><IconBack /> Заявка</Link>
        <PrintButton />
      </div>
      <article className="card" style={{ marginTop: 10, padding: 22 }}>
        <div className="t2" style={{ textAlign: "center", fontWeight: 700, color: "var(--bad)" }}>ОБРАЗЕЦ · КОНЦЕПТ ДЛЯ КОНКУРСА · НЕ ЯВЛЯЕТСЯ ДОКУМЕНТОМ</div>
        <h1 style={{ fontSize: 22, textAlign: "center", margin: "14px 0 4px" }}>СПРАВКА № {r.number}</h1>
        <div className="t2" style={{ textAlign: "center" }}>выдана {humanDate(issued, false)} {issued.slice(0, 4)} г.</div>
        <p style={{ marginTop: 18, lineHeight: 1.6, fontSize: 16 }}>
          Настоящая справка подтверждает, что {user.last_name} {user.first_name} {user.middle_name} {user.gender === "f" ? "является студенткой" : user.gender === "m" ? "является студентом" : "обучается на"} {user.course} {user.gender ? "курса" : "курсе"}{" "}
          очной формы обучения, направление «{user.program}», {user.faculty.toLowerCase()}, группа {user.group_name}.
        </p>
        <p style={{ marginTop: 10, lineHeight: 1.6 }}>Справка выдана {String(JSON.parse(r.details).place ?? "по месту требования").toLowerCase()}.</p>
        <div style={{ display: "flex", gap: 16, alignItems: "center", marginTop: 20, flexWrap: "wrap" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={qr} alt="QR-код для проверки справки" width={140} height={140} />
          <div className="t2">Подлинность можно проверить по QR-коду или по адресу<br /><b style={{ wordBreak: "break-all" }}>{verifyUrl}</b></div>
        </div>
        <div className="t2" style={{ marginTop: 18 }}>Учебный офис · электронная подпись (имитация)</div>
      </article>
    </>
  );
}
