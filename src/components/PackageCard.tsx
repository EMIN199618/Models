"use client";

import Link from "next/link";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import { createOrderAction, type OrderState } from "@/actions/orders";
import {
  CREDIT_VALIDITY_DAYS,
  formatCredits,
  formatMinor,
  MODEL_CREDIT_COST,
  type CreditPackage,
} from "@/lib/pricing";

function SubmitButton({ featured }: { featured: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className={featured ? "btn-primary w-full" : "btn-ghost w-full"}
      disabled={pending}
    >
      {pending ? "Göndərilir…" : "Sifariş et"}
    </button>
  );
}

export function PackageCard({
  pkg,
  isLoggedIn,
  hasPending,
}: {
  pkg: CreditPackage;
  isLoggedIn: boolean;
  hasPending: boolean;
}) {
  const [state, formAction] = useActionState<OrderState, FormData>(
    createOrderAction,
    undefined,
  );

  const modelCount = Math.floor(pkg.credits / MODEL_CREDIT_COST);
  const ordered = state?.ok || hasPending;

  return (
    <div
      className={`relative flex flex-col rounded-xl border bg-surface p-6 ${
        pkg.featured ? "border-accent" : "border-border"
      }`}
    >
      {pkg.featured && (
        <span className="absolute -top-2.5 left-6 rounded bg-accent px-2 py-0.5 text-[11px] font-semibold text-white">
          Ən çox seçilən
        </span>
      )}

      <h3 className="text-sm font-semibold text-muted">{pkg.name}</h3>

      <p className="mt-2 text-3xl font-semibold">
        {formatMinor(pkg.priceMinor, pkg.currency)}
      </p>

      <p className="mt-1 text-accent">
        {formatCredits(pkg.credits)} Credit
      </p>

      <ul className="mt-5 space-y-2 text-sm text-muted">
        <li className="flex gap-2">
          <span className="text-success">✓</span>
          <span>
            <strong className="text-foreground">{modelCount}</strong> model endirmə
          </span>
        </li>
        <li className="flex gap-2">
          <span className="text-success">✓</span>
          <span>Bir model = {MODEL_CREDIT_COST} Credit</span>
        </li>
        <li className="flex gap-2">
          <span className="text-success">✓</span>
          <span>
            Credit-lər <strong className="text-foreground">{CREDIT_VALIDITY_DAYS} gün</strong>{" "}
            etibarlıdır
          </span>
        </li>
        <li className="flex gap-2">
          <span className="text-success">✓</span>
          <span>Endirilən fayl həmişəlik sizindir</span>
        </li>
      </ul>

      <div className="mt-6">
        {!isLoggedIn ? (
          <Link href="/login" className="btn-ghost w-full">
            Almaq üçün daxil olun
          </Link>
        ) : ordered ? (
          <div className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-center text-xs text-warning">
            Sifariş qeydə alındı — ödəniş təsdiqi gözlənilir
          </div>
        ) : (
          <form action={formAction}>
            <input type="hidden" name="packageId" value={pkg.id} />
            <SubmitButton featured={pkg.featured ?? false} />
          </form>
        )}

        {state?.error && (
          <p className="mt-2 text-center text-xs text-danger">{state.error}</p>
        )}
      </div>
    </div>
  );
}
