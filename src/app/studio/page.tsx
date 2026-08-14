import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export const metadata = { title: "Studiya" };

const STATUS_LABEL: Record<string, { text: string; className: string }> = {
  DRAFT: { text: "Qaralama", className: "text-muted" },
  PENDING: { text: "Moderasiyada", className: "text-warning" },
  PUBLISHED: { text: "Dərc olunub", className: "text-success" },
  REJECTED: { text: "Rədd edilib", className: "text-danger" },
  ARCHIVED: { text: "Arxivləşdirilib", className: "text-muted" },
};

export default async function StudioPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "ARTIST" && user.role !== "ADMIN") redirect("/models");

  const uploaded = (await searchParams).uploaded === "1";

  const models = await prisma.model.findMany({
    where: { authorId: user.id },
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      slug: true,
      title: true,
      status: true,
      creditCost: true,
      downloadCount: true,
      viewCount: true,
      rejectionReason: true,
      createdAt: true,
      assets: {
        where: { kind: "IMAGE" },
        orderBy: { sortOrder: "asc" },
        take: 1,
        select: { storageKey: true },
      },
    },
  });

  const published = models.filter((m) => m.status === "PUBLISHED");
  const totalDownloads = published.reduce((s, m) => s + m.downloadCount, 0);
  const earnedCredits = published.reduce((s, m) => s + m.downloadCount * m.creditCost, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Studiya</h1>
          <p className="text-sm text-muted">Modellərinizi idarə edin</p>
        </div>
        <Link href="/studio/new" className="btn-primary">
          Yeni model yüklə
        </Link>
      </div>

      {uploaded && (
        <p className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
          Model yükləndi və moderasiya növbəsinə göndərildi.
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Modellər" value={models.length} />
        <Stat label="Dərc olunub" value={published.length} />
        <Stat label="Endirilmə" value={totalDownloads} />
        <Stat label="Qazanılan Credit" value={earnedCredits} hint="brüt" />
      </div>

      {models.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-sm text-muted">Hələ model yükləməmisiniz.</p>
          <Link href="/studio/new" className="mt-3 inline-block text-sm text-accent hover:underline">
            İlk modelinizi yükləyin
          </Link>
        </div>
      ) : (
        <div className="card divide-y divide-border">
          {models.map((m) => {
            const status = STATUS_LABEL[m.status] ?? STATUS_LABEL.DRAFT;
            return (
              <div key={m.id} className="flex items-center gap-4 p-4">
                <div className="relative size-16 shrink-0 overflow-hidden rounded-lg bg-surface-2">
                  {m.assets[0] && (
                    <Image
                      src={`/uploads/${m.assets[0].storageKey}`}
                      alt={m.title}
                      fill
                      sizes="64px"
                      className="object-cover"
                    />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {m.status === "PUBLISHED" ? (
                      <Link href={`/models/${m.slug}`} className="truncate font-medium hover:text-accent">
                        {m.title}
                      </Link>
                    ) : (
                      <span className="truncate font-medium">{m.title}</span>
                    )}
                    <span className={`text-xs ${status.className}`}>· {status.text}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted">
                    {m.creditCost} Credit · {m.viewCount} baxış · {m.downloadCount} endirilmə
                  </p>
                  {m.status === "REJECTED" && m.rejectionReason && (
                    <p className="mt-1 text-xs text-danger">Səbəb: {m.rejectionReason}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-muted">
        {label}
        {hint && <span className="opacity-60"> ({hint})</span>}
      </p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
