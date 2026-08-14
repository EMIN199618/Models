"use client";

import Link from "next/link";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import { purchaseAction } from "@/actions/models";

function SubmitButton({ cost }: { cost: number }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="btn-primary w-full" disabled={pending}>
      {pending
        ? "Emal olunur…"
        : cost === 0
          ? "Pulsuz əldə et"
          : `${cost} Credit ilə əldə et`}
    </button>
  );
}

export function PurchaseBox({
  slug,
  modelId,
  creditCost,
  owned,
  isLoggedIn,
  balance,
}: {
  slug: string;
  modelId: string;
  creditCost: number;
  owned: boolean;
  isLoggedIn: boolean;
  balance: number;
}) {
  const [state, formAction] = useActionState(purchaseAction, undefined);
  const justPurchased = state?.ok === true;

  if (!isLoggedIn) {
    return (
      <div className="card space-y-3 p-4">
        <PriceRow creditCost={creditCost} />
        <Link href="/login" className="btn-primary w-full">
          Endirmək üçün daxil olun
        </Link>
        <p className="text-xs text-muted">
          Qeydiyyatdan keçənlərə 5 Credit hədiyyə verilir.
        </p>
      </div>
    );
  }

  if (owned || justPurchased) {
    return (
      <div className="card space-y-3 p-4">
        <p className="flex items-center gap-2 text-sm text-success">
          <span aria-hidden>✓</span> Bu model sizindir
        </p>
        <a href={`/api/download/${modelId}`} className="btn-primary w-full">
          Faylı endir
        </a>
        <p className="text-xs text-muted">
          Təkrar endirmələr pulsuzdur — Credit yenidən tutulmur.
        </p>
      </div>
    );
  }

  const insufficient = balance < creditCost;

  return (
    <div className="card space-y-3 p-4">
      <PriceRow creditCost={creditCost} />

      <form action={formAction}>
        <input type="hidden" name="slug" value={slug} />
        <SubmitButton cost={creditCost} />
      </form>

      <p className="text-xs text-muted">
        Balansınız: <span className="text-foreground">{balance} Credit</span>
      </p>

      {insufficient && creditCost > 0 && (
        <p className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
          Balansınız kifayət etmir. Credit paketi almaq üçün abunə bölməsinə keçin.
        </p>
      )}

      {state?.error && (
        <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          {state.error}
        </p>
      )}
    </div>
  );
}

function PriceRow({ creditCost }: { creditCost: number }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-sm text-muted">Qiymət</span>
      <span className="text-xl font-semibold">
        {creditCost === 0 ? "Pulsuz" : `${creditCost} Credit`}
      </span>
    </div>
  );
}
