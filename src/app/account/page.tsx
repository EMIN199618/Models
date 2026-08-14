import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { cancelOrderAction } from "@/actions/orders";
import { ReferralBox } from "@/components/ReferralBox";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { formatCredits, formatMinor, MODEL_CREDIT_COST } from "@/lib/pricing";

export const metadata = { title: "Hesabım" };

const REASON_LABEL: Record<string, string> = {
  SIGNUP_BONUS: "Qeydiyyat hədiyyəsi",
  ADMIN_GRANT: "Admin tərəfindən əlavə",
  SUBSCRIPTION: "Abunə krediti",
  CREDIT_PACKAGE: "Credit paketi",
  REFERRAL: "Dəvət bonusu",
  DOWNLOAD_SPEND: "Model əldə edilməsi",
  REFUND: "Geri qaytarma",
};

const ORDER_STATUS: Record<string, { text: string; className: string }> = {
  PENDING: { text: "Ödəniş gözlənilir", className: "text-warning" },
  PAID: { text: "Ödənilib", className: "text-success" },
  CANCELED: { text: "Ləğv edilib", className: "text-muted" },
};

export default async function AccountPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  // Dəvət linkinin tam ünvanı serverdə hazırlanır (hydration uyğunsuzluğu olmasın).
  const h = await headers();
  const host = h.get("host") ?? "";
  const proto = h.get("x-forwarded-proto") ?? "http";
  const origin = host ? `${proto}://${host}` : "";

  const [transactions, entitlements, profile, orders] = await Promise.all([
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
      select: { referralCode: true, _count: { select: { referrals: true } } },
    }),
    prisma.creditOrder.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "desc" },
      take: 10,
      select: {
        id: true,
        packageId: true,
        credits: true,
        priceMinor: true,
        currency: true,
        status: true,
        createdAt: true,
      },
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
          <p className="mt-1 text-3xl font-semibold text-accent">
            {formatCredits(user.creditBalance)}
          </p>
          <p className="mt-1 text-xs text-muted">
            ≈ {Math.floor(user.creditBalance / MODEL_CREDIT_COST)} model
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">Əldə edilmiş model</p>
          <p className="mt-1 text-3xl font-semibold">{entitlements.length}</p>
        </div>
        <div className="card flex flex-col justify-between p-5">
          <p className="text-xs text-muted">Credit lazımdır?</p>
          <Link href="/pricing" className="btn-primary mt-2">
            Paketlərə bax
          </Link>
        </div>
      </div>

      {profile && (
        <ReferralBox
          code={profile.referralCode}
          invitedCount={profile._count.referrals}
          origin={origin}
        />
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold">Credit sifarişlərim</h2>
        {orders.length === 0 ? (
          <p className="card p-8 text-center text-sm text-muted">
            Hələ sifariş verməmisiniz.
          </p>
        ) : (
          <div className="card divide-y divide-border text-sm">
            {orders.map((o) => (
              <div key={o.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-40 flex-1">
                  <p className="font-medium capitalize">{o.packageId}</p>
                  <p className="text-xs text-muted">
                    {formatCredits(o.credits)} Credit ·{" "}
                    {formatMinor(o.priceMinor, o.currency)} ·{" "}
                    {o.createdAt.toLocaleDateString("az-AZ")}
                  </p>
                </div>
                <span className={`text-xs ${ORDER_STATUS[o.status].className}`}>
                  {ORDER_STATUS[o.status].text}
                </span>
                {o.status === "PENDING" && (
                  <form action={cancelOrderAction}>
                    <input type="hidden" name="orderId" value={o.id} />
                    <button type="submit" className="btn-ghost text-xs">
                      Ləğv et
                    </button>
                  </form>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

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
