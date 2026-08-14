"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import type { ActionState } from "@/actions/auth";

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="btn-primary w-full" disabled={pending}>
      {pending ? "Gözləyin…" : label}
    </button>
  );
}

export function AuthForm({
  mode,
  action,
}: {
  mode: "login" | "register";
  action: (prev: ActionState, formData: FormData) => Promise<ActionState>;
}) {
  const [state, formAction] = useActionState(action, undefined);
  const isRegister = mode === "register";

  return (
    <form action={formAction} className="space-y-4">
      {isRegister && (
        <div>
          <label className="label" htmlFor="name">
            Ad və soyad
          </label>
          <input id="name" name="name" className="input" required autoComplete="name" />
        </div>
      )}

      <div>
        <label className="label" htmlFor="email">
          E-poçt
        </label>
        <input
          id="email"
          name="email"
          type="email"
          className="input"
          required
          autoComplete="email"
        />
      </div>

      <div>
        <label className="label" htmlFor="password">
          Parol
        </label>
        <input
          id="password"
          name="password"
          type="password"
          className="input"
          required
          minLength={isRegister ? 8 : undefined}
          autoComplete={isRegister ? "new-password" : "current-password"}
        />
        {isRegister && (
          <p className="mt-1 text-xs text-muted">Ən azı 8 simvol.</p>
        )}
      </div>

      {isRegister && (
        <label className="flex items-start gap-2.5 rounded-lg border border-border bg-surface-2 p-3">
          <input
            type="checkbox"
            name="isArtist"
            className="mt-0.5 accent-[var(--accent)]"
          />
          <span className="text-sm">
            Artist kimi qeydiyyatdan keçirəm
            <span className="mt-0.5 block text-xs text-muted">
              Model yükləyə, profil və statistika görə biləcəksiniz.
            </span>
          </span>
        </label>
      )}

      {state?.error && (
        <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {state.error}
        </p>
      )}

      <SubmitButton label={isRegister ? "Qeydiyyatdan keç" : "Daxil ol"} />
    </form>
  );
}
