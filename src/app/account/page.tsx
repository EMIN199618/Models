import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export const metadata = { title: "Hesabım" };

const REASON_LABEL: Record<string, string> = {
  SIGNUP_BONUS: "Qeydiyyat hədiyyəsi",
  ADMIN_GRANT: "Admin tərəfindən əlavə",
  SUBSCRIPTION: "Abunə krediti",
  REFERRAL: "Dəvət bonusu",
  DOWNLOAD_SPEND: "Model əldə edilməsi",
  REFUND: "Geri qaytarma",
};

export default async function AccountPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const [transactions, entitlements, referralCode] = await Promise.all([
    prisma.creditTransaction.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "desc" },
      take: 30,
      select: {
        id: true,
        amount: true,
        reason: true,
        balanceAfter: true,
        createdAt: true,
        model: { select: { title: true, slug: true } },
      },
    }),
    prisma.entitlement.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        creditsSpent: true,
        createdAt: true,
        model: { select: { id: true, slug: true, title: true, status: true } },
      },
    }),
    prisma.user.findUnique({
      where: { id: user.id },
      select: { referralCode: true },
    }),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">{user.name}</h1>
        <p className="text-sm text-muted">{user.email}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card p-5">
          <p className="text-xs text-muted">Credit balansı</p>
          <p className="mt-1 text-3xl font-semibold text-accent">{user.creditBalance}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">Əldə edilmiş model</p>
          <p className="mt-1 text-3xl font-semibold">{entitlements.length}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">Dəvət kodunuz</p>
          <p className="mt-1 truncate font-mono text-sm">{referralCode?.referralCode}</p>
        </div>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Modellərim</h2>
        {entitlements.length === 0 ? (
          <div className="card p-8 text-center">
            <p className="text-sm text-muted">Hələ model əldə etməmisiniz.</p>
            <Link href="/models" className="mt-2 inline-block text-sm text-accent hover:underline">
              Kataloqa keç
            </Link>
          </div>
        ) : (
          <div className="card divide-y divide-border">
            {entitlements.map((e) => (
              <div key={e.id} className="flex items-center gap-4 p-4">
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/models/${e.model.slug}`}
                    className="truncate font-medium hover:text-accent"
                  >
                    {e.model.title}
                  </Link>
                  <p className="text-xs text-muted">
                    {e.creditsSpent} Credit ·{" "}
                    {e.createdAt.toLocaleDateString("az-AZ")}
                  </p>
                </div>
                {e.model.status === "PUBLISHED" ? (
                  <a href={`/api/download/${e.model.id}`} className="btn-ghost text-xs">
                    Endir
                  </a>
                ) : (
                  <span className="text-xs text-muted">Əlçatan deyil</span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Credit hərəkatı</h2>
        {transactions.length === 0 ? (
          <p className="card p-8 text-center text-sm text-muted">Hərəkat yoxdur.</p>
        ) : (
          <div className="card divide-y divide-border text-sm">
            {transactions.map((t) => (
              <div key={t.id} className="flex items-center gap-4 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate">
                    {REASON_LABEL[t.reason] ?? t.reason}
                    {t.model && (
                      <span className="text-muted"> — {t.model.title}</span>
                    )}
                  </p>
                  <p className="text-xs text-muted">
                    {t.createdAt.toLocaleString("az-AZ")}
                  </p>
                </div>
                <span
                  className={`font-medium ${t.amount > 0 ? "text-success" : "text-danger"}`}
                >
                  {t.amount > 0 ? "+" : ""}
                  {t.amount}
                </span>
                <span className="w-12 text-right text-xs text-muted">{t.balanceAfter}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
