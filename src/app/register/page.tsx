import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/AuthForm";
import { registerAction } from "@/actions/auth";
import { getCurrentUser } from "@/lib/auth";
import { MODEL_CREDIT_COST, REFERRAL_BONUS_CREDITS } from "@/lib/pricing";

export const metadata = { title: "Qeydiyyat" };

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (await getCurrentUser()) redirect("/models");

  // Dost linki: /register?ref=KOD — kod avtomatik doldurulur
  const params = await searchParams;
  const ref = typeof params.ref === "string" ? params.ref : "";

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-1 text-2xl font-semibold">Qeydiyyat</h1>
      <p className="mb-6 text-sm text-muted">
        Dəvət kodu ilə qeydiyyatdan keçənlərə{" "}
        <span className="text-accent">{REFERRAL_BONUS_CREDITS} Credit</span> hədiyyə
        ({REFERRAL_BONUS_CREDITS / MODEL_CREDIT_COST} model).
      </p>

      <div className="card p-6">
        <AuthForm mode="register" action={registerAction} defaultReferralCode={ref} />
      </div>

      <p className="mt-4 text-center text-sm text-muted">
        Artıq hesabınız var?{" "}
        <Link href="/login" className="text-accent hover:underline">
          Daxil olun
        </Link>
      </p>
    </div>
  );
}
