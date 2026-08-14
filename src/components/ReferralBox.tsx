"use client";

import { useState } from "react";

import { MODEL_CREDIT_COST, REFERRAL_BONUS_CREDITS } from "@/lib/pricing";

/** Dəvət kodu və hazır dəvət linki — bir klikə kopyalanır. */
export function ReferralBox({
  code,
  invitedCount,
  origin,
}: {
  code: string;
  invitedCount: number;
  /** Saytın ünvanı — serverdən gəlir ki, hydration uyğunsuzluğu olmasın. */
  origin: string;
}) {
  const [copied, setCopied] = useState<"code" | "link" | null>(null);

  const link = `${origin}/register?ref=${code}`;

  async function copy(value: string, which: "code" | "link") {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(which);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Buferə giriş qadağandırsa, istifadəçi əl ilə seçə bilər
    }
  }

  return (
    <section className="card p-5">
      <h2 className="text-lg font-semibold">Dostunu dəvət et</h2>
      <p className="mt-1 text-sm text-muted">
        Dostunuz qeydiyyat zamanı bu kodu yazsa,{" "}
        <strong className="text-foreground">{REFERRAL_BONUS_CREDITS} Credit</strong>{" "}
        hədiyyə qazanır ({REFERRAL_BONUS_CREDITS / MODEL_CREDIT_COST} model).
      </p>

      <div className="mt-4 space-y-3">
        <div>
          <span className="label">Dəvət kodunuz</span>
          <div className="flex gap-2">
            <code className="flex-1 truncate rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-sm">
              {code}
            </code>
            <button
              type="button"
              onClick={() => copy(code, "code")}
              className="btn-ghost shrink-0 text-xs"
            >
              {copied === "code" ? "Kopyalandı ✓" : "Kopyala"}
            </button>
          </div>
        </div>

        <div>
          <span className="label">Hazır dəvət linki</span>
          <div className="flex gap-2">
            <code className="flex-1 truncate rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-xs">
              {link}
            </code>
            <button
              type="button"
              onClick={() => copy(link, "link")}
              className="btn-ghost shrink-0 text-xs"
            >
              {copied === "link" ? "Kopyalandı ✓" : "Kopyala"}
            </button>
          </div>
          <p className="mt-1 text-xs text-muted">
            Bu linklə gələndə kod avtomatik doldurulur.
          </p>
        </div>
      </div>

      <p className="mt-4 border-t border-border pt-3 text-sm">
        Dəvət etdiyiniz:{" "}
        <strong className="text-accent">{invitedCount}</strong> nəfər
      </p>
    </section>
  );
}
