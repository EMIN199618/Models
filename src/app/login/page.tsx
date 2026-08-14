import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/AuthForm";
import { loginAction } from "@/actions/auth";
import { getCurrentUser } from "@/lib/auth";

export const metadata = { title: "Giriş" };

export default async function LoginPage() {
  if (await getCurrentUser()) redirect("/models");

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-1 text-2xl font-semibold">Daxil ol</h1>
      <p className="mb-6 text-sm text-muted">Hesabınıza daxil olun.</p>

      <div className="card p-6">
        <AuthForm mode="login" action={loginAction} />
      </div>

      <p className="mt-4 text-center text-sm text-muted">
        Hesabınız yoxdur?{" "}
        <Link href="/register" className="text-accent hover:underline">
          Qeydiyyatdan keçin
        </Link>
      </p>
    </div>
  );
}
