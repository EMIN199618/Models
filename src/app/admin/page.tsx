import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";

import {
  approveModelAction,
  archiveModelAction,
  cancelOrderAdminAction,
  grantCreditsAction,
  markOrderPaidAction,
  rejectModelAction,
  resolveReportAction,
} from "@/actions/admin";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { formatCredits, formatMinor } from "@/lib/pricing";

export const metadata = { title: "Admin" };

export default async function AdminPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "ADMIN") redirect("/models");

  const [pending, orders, reports, counts] = await Promise.all([
    prisma.model.findMany({
      where: { status: "PENDING" },
      orderBy: { createdAt: "asc" },
      select: {
        id: true,
        title: true,
        creditCost: true,
        renderer: true,
        formats: true,
        createdAt: true,
        author: { select: { name: true, email: true } },
        assets: {
          where: { kind: "IMAGE" },
          orderBy: { sortOrder: "asc" },
          take: 1,
          select: { storageKey: true },
        },
      },
    }),
    prisma.creditOrder.findMany({
      where: { status: "PENDING" },
      orderBy: { createdAt: "asc" },
      select: {
        id: true,
        packageId: true,
        credits: true,
        priceMinor: true,
        currency: true,
        createdAt: true,
        user: { select: { name: true, email: true } },
      },
    }),
    prisma.report.findMany({
      where: { status: "OPEN" },
      orderBy: { createdAt: "asc" },
      take: 20,
      select: {
        id: true,
        reason: true,
        details: true,
        createdAt: true,
        model: { select: { id: true, slug: true, title: true } },
      },
    }),
    Promise.all([
      prisma.user.count(),
      prisma.model.count({ where: { status: "PUBLISHED" } }),
      prisma.entitlement.count(),
    ]),
  ]);

  const [userCount, publishedCount, saleCount] = counts;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Admin paneli</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="İstifadəçi" value={userCount} />
        <Stat label="Dərc olunmuş model" value={publishedCount} />
        <Stat label="Endirmə hüququ" value={saleCount} />
        <Stat label="Moderasiyada" value={pending.length} />
      </div>

      {/* Credit vermə */}
      <section className="card p-5">
        <h2 className="mb-3 text-sm font-semibold text-muted">Credit əlavə et</h2>
        <form action={grantCreditsAction} className="flex flex-wrap items-end gap-3">
          <div className="min-w-56 flex-1">
            <label className="label" htmlFor="grant-email">
              İstifadəçi e-poçtu
            </label>
            <input id="grant-email" name="email" type="email" className="input" required />
          </div>
          <div className="w-32">
            <label className="label" htmlFor="grant-amount">
              Credit
            </label>
            <input
              id="grant-amount"
              name="amount"
              type="number"
              min={1}
              max={10000}
              defaultValue={50}
              className="input"
              required
            />
          </div>
          <button type="submit" className="btn-primary">
            Əlavə et
          </button>
        </form>
        <p className="mt-2 text-xs text-muted">
          Ödəniş şlüzü qoşulanadək abunə və Credit satışı bu yolla idarə olunur.
        </p>
      </section>

      {/* Credit paketi sifarişləri */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">
          Gözləyən Credit sifarişləri{" "}
          <span className="text-sm font-normal text-muted">({orders.length})</span>
        </h2>

        {orders.length === 0 ? (
          <p className="card p-8 text-center text-sm text-muted">
            Gözləyən sifariş yoxdur.
          </p>
        ) : (
          <div className="card divide-y divide-border">
            {orders.map((o) => (
              <div key={o.id} className="flex flex-wrap items-center gap-4 p-4">
                <div className="min-w-56 flex-1">
                  <p className="font-medium capitalize">
                    {o.packageId} — {formatCredits(o.credits)} Credit
                  </p>
                  <p className="mt-0.5 text-xs text-muted">
                    {o.user.name} ({o.user.email}) ·{" "}
                    {o.createdAt.toLocaleDateString("az-AZ")}
                  </p>
                </div>

                <span className="font-semibold">
                  {formatMinor(o.priceMinor, o.currency)}
                </span>

                <div className="flex gap-2">
                  <form action={markOrderPaidAction}>
                    <input type="hidden" name="orderId" value={o.id} />
                    <button type="submit" className="btn-primary text-xs">
                      Ödənildi — Credit ver
                    </button>
                  </form>
                  <form action={cancelOrderAdminAction}>
                    <input type="hidden" name="orderId" value={o.id} />
                    <button type="submit" className="btn-ghost text-xs">
                      Ləğv et
                    </button>
                  </form>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Moderasiya növbəsi */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">
          Moderasiya növbəsi{" "}
          <span className="text-sm font-normal text-muted">({pending.length})</span>
        </h2>

        {pending.length === 0 ? (
          <p className="card p-8 text-center text-sm text-muted">
            Gözləyən model yoxdur.
          </p>
        ) : (
          <div className="space-y-3">
            {pending.map((m) => (
              <div key={m.id} className="card flex flex-wrap items-start gap-4 p-4">
                <div className="relative size-20 shrink-0 overflow-hidden rounded-lg bg-surface-2">
                  {m.assets[0] && (
                    <Image
                      src={`/uploads/${m.assets[0].storageKey}`}
                      alt={m.title}
                      fill
                      sizes="80px"
                      className="object-cover"
                    />
                  )}
                </div>

                <div className="min-w-56 flex-1">
                  <h3 className="font-medium">{m.title}</h3>
                  <p className="mt-0.5 text-xs text-muted">
                    {m.author.name} ({m.author.email})
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {m.creditCost} Credit · {m.renderer} ·{" "}
                    {m.formats.map((f) => f.toUpperCase()).join(", ") || "format yoxdur"}
                  </p>
                </div>

                <div className="flex flex-col gap-2">
                  <form action={approveModelAction}>
                    <input type="hidden" name="modelId" value={m.id} />
                    <button type="submit" className="btn-primary w-full text-xs">
                      Təsdiqlə
                    </button>
                  </form>

                  <form action={rejectModelAction} className="flex gap-2">
                    <input type="hidden" name="modelId" value={m.id} />
                    <input
                      name="reason"
                      className="input w-44 text-xs"
                      placeholder="Rədd səbəbi"
                      required
                      minLength={3}
                    />
                    <button type="submit" className="btn-danger text-xs">
                      Rədd et
                    </button>
                  </form>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Şikayətlər */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">
          Açıq şikayətlər{" "}
          <span className="text-sm font-normal text-muted">({reports.length})</span>
        </h2>

        {reports.length === 0 ? (
          <p className="card p-8 text-center text-sm text-muted">Açıq şikayət yoxdur.</p>
        ) : (
          <div className="card divide-y divide-border">
            {reports.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center gap-4 p-4">
                <div className="min-w-56 flex-1">
                  <Link
                    href={`/models/${r.model.slug}`}
                    className="font-medium hover:text-accent"
                  >
                    {r.model.title}
                  </Link>
                  <p className="mt-0.5 text-xs text-danger">{r.reason}</p>
                  {r.details && <p className="mt-1 text-xs text-muted">{r.details}</p>}
                </div>

                <div className="flex gap-2">
                  <form action={archiveModelAction}>
                    <input type="hidden" name="modelId" value={r.model.id} />
                    <button type="submit" className="btn-danger text-xs">
                      Modeli arxivlə
                    </button>
                  </form>
                  <form action={resolveReportAction}>
                    <input type="hidden" name="reportId" value={r.id} />
                    <input type="hidden" name="status" value="RESOLVED" />
                    <button type="submit" className="btn-ghost text-xs">
                      Həll edildi
                    </button>
                  </form>
                  <form action={resolveReportAction}>
                    <input type="hidden" name="reportId" value={r.id} />
                    <input type="hidden" name="status" value="DISMISSED" />
                    <button type="submit" className="btn-ghost text-xs">
                      Rədd et
                    </button>
                  </form>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
