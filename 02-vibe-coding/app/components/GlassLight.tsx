"use client";
import { useEffect } from "react";

/** Блик на стеклянных элементах следует за курсором (только мышь, без анимации при reduced motion). */
export default function GlassLight() {
  useEffect(() => {
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let last: HTMLElement | null = null;
    const onMove = (e: PointerEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const el = (e.target as Element | null)?.closest?.<HTMLElement>(".glass, .card.hero") ?? null;
        if (last && last !== el) { last.style.removeProperty("--mx"); last.style.removeProperty("--my"); }
        last = el;
        if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", `${(((e.clientX - r.left) / r.width) * 100).toFixed(1)}%`);
        el.style.setProperty("--my", `${(((e.clientY - r.top) / r.height) * 100).toFixed(1)}%`);
      });
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => { document.removeEventListener("pointermove", onMove); cancelAnimationFrame(frame); };
  }, []);
  return null;
}
