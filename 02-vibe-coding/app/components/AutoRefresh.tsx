"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Обновляет данные страницы раз в 20 секунд и при возвращении на вкладку:
 *  так перенос пары или новый статус заявки студент видит без перезагрузки. */
export default function AutoRefresh({ seconds = 20 }: { seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    const tick = () => { if (document.visibilityState === "visible") router.refresh(); };
    const id = setInterval(tick, seconds * 1000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", tick); };
  }, [router, seconds]);
  return null;
}
