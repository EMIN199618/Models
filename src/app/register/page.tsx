import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/AuthForm";
import { registerAction } from "@/actions/auth";
import { getCurrentUser } from "@/lib/auth";

export const metadata = { title: "Qeydiyyat" };

export default async function RegisterPage() {
  if (await getCurrentUser()) redirect("/models");

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-1 text-2xl font-semibold">Qeydiyyat</h1>
      <p className="mb-6 text-sm text-muted">
        Qeydiyyatdan keçən hər kəsə <span className="text-accent">5 Credit</span> hədiyyə.
      </p>

      <div className="card p-6">
        <AuthForm mode="register" action={registerAction} />
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
