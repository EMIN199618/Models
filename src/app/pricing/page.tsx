import { PackageCard } from "@/components/PackageCard";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import {
  ARTIST_REVENUE_SHARE,
  CREDIT_PACKAGES,
  formatCredits,
  MODEL_CREDIT_COST,
  REFERRAL_BONUS_CREDITS,
} from "@/lib/pricing";

export const metadata = { title: "Qiymətlər" };

export default async function PricingPage() {
  const user = await getCurrentUser();

  const pending = user
    ? await prisma.creditOrder.findMany({
        where: { userId: user.id, status: "PENDING" },
        select: { packageId: true },
      })
    : [];
  const pendingIds = new Set(pending.map((o) => o.packageId));

  return (
    <div className="space-y-12">
      <header className="text-center">
        <h1 className="text-3xl font-semibold">Credit paketləri</h1>
        <p className="mx-auto mt-3 max-w-2xl text-muted">
          Kataloqdakı hər model {MODEL_CREDIT_COST} Credit-dir. Credit alıb
          istədiyiniz modeli endirin — abunə məcburiyyəti yoxdur, Credit-lərin
          müddəti bitmir.
        </p>
        {user && (
          <p className="mt-3 text-sm">
            Cari balansınız:{" "}
            <span className="font-semibold text-accent">
              {formatCredits(user.creditBalance)} Credit
            </span>
          </p>
        )}
      </header>

      <div className="grid gap-5 md:grid-cols-3">
        {CREDIT_PACKAGES.map((pkg) => (
          <PackageCard
            key={pkg.id}
            pkg={pkg}
            isLoggedIn={user !== null}
            hasPending={pendingIds.has(pkg.id)}
          />
        ))}
      </div>

      <section className="rounded-xl border border-border bg-surface p-6">
        <h2 className="text-lg font-semibold">Ödəniş necə aparılır?</h2>
        <p className="mt-2 text-sm text-muted">
          Onlayn ödəniş şlüzü hazırlıq mərhələsindədir. Hazırda &laquo;Sifariş
          et&raquo; düyməsi sifarişi qeydə alır; ödəniş təsdiqləndikdən sonra
          Credit-lər balansınıza köçürülür və e-poçtla məlumat verilir.
        </p>
      </section>

      <div className="grid gap-5 md:grid-cols-2">
        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold">Artistlər üçün</h2>
          <p className="mt-2 text-sm text-muted">
            Model yükləmək tamamilə pulsuzdur. Modeliniz hər dəfə endiriləndə
            gəlirin{" "}
            <strong className="text-foreground">
              {Math.round(ARTIST_REVENUE_SHARE * 100)}%
            </strong>{" "}
            sizə düşür, {Math.round((1 - ARTIST_REVENUE_SHARE) * 100)}% platformada
            qalır. Qazancınızı Studiya bölməsində izləyə bilərsiniz.
          </p>
        </section>

        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold">Dostunu dəvət et</h2>
          <p className="mt-2 text-sm text-muted">
            Qeydiyyatdan keçən hər kəsə şəxsi dəvət kodu verilir. Dostunuz
            qeydiyyat zamanı sizin kodunuzu yazsa,{" "}
            <strong className="text-foreground">
              {REFERRAL_BONUS_CREDITS} Credit
            </strong>{" "}
            hədiyyə qazanır — bu, {REFERRAL_BONUS_CREDITS / MODEL_CREDIT_COST}{" "}
            pulsuz model deməkdir.
          </p>
        </section>
      </div>
    </div>
  );
}
