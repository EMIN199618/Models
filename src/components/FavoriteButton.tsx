"use client";

import { useState, useTransition } from "react";

import { toggleFavoriteAction } from "@/actions/models";

/**
 * Seçilmişlərə əlavə/çıxarma. Optimist yenilənir — server cavabını
 * gözləmədən ikon dəyişir, xəta olarsa geri qaytarılır.
 */
export function FavoriteButton({ slug, initial }: { slug: string; initial: boolean }) {
  const [active, setActive] = useState(initial);
  const [pending, startTransition] = useTransition();

  return (
    <button
      type="button"
      disabled={pending}
      aria-pressed={active}
      aria-label={active ? "Seçilmişlərdən çıxar" : "Seçilmişlərə əlavə et"}
      title={active ? "Seçilmişlərdən çıxar" : "Seçilmişlərə əlavə et"}
      onClick={() => {
        const next = !active;
        setActive(next);
        startTransition(async () => {
          const result = await toggleFavoriteAction(slug);
          // Server "giriş lazımdır" desə və ya xəta olsa, əvvəlki hala qayıt.
          if (!result.ok) setActive(!next);
          else setActive(result.favorited);
        });
      }}
      className={`flex size-7 items-center justify-center rounded-md border backdrop-blur transition-colors ${
        active
          ? "border-danger/60 bg-danger/20 text-danger"
          : "border-white/25 bg-black/50 text-white hover:border-white/50"
      }`}
    >
      <svg viewBox="0 0 24 24" className="size-3.5" aria-hidden>
        <path
          d="M12 21s-7.5-4.7-9.5-9A5.2 5.2 0 0 1 12 6.5 5.2 5.2 0 0 1 21.5 12c-2 4.3-9.5 9-9.5 9z"
          fill={active ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
