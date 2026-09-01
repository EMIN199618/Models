import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { deleteReviewAction } from "@/actions/reviews";
import { ModelViewer } from "@/components/ModelViewer";
import { PurchaseBox } from "@/components/PurchaseBox";
import { ReviewForm } from "@/components/ReviewForm";
import { ReviewStars } from "@/components/ReviewStars";
import { formatPolys } from "@/components/ModelCard";
import { getCurrentUser } from "@/lib/auth";
import { hasEntitlement } from "@/lib/credits";
import { prisma } from "@/lib/prisma";
import { formatCredits } from "@/lib/pricing";

const RENDERER_LABEL: Record<string, string> = {
  CORONA: "Corona Renderer",
  VRAY: "V-Ray",
  BOTH: "Corona + V-Ray",
  OTHER: "Digər",
};

async function getModel(slug: string) {
  return prisma.model.findUnique({
    where: { slug },
    select: {
      id: true,
      slug: true,
      title: true,
      description: true,
      status: true,
      creditCost: true,
      renderer: true,
      formats: true,
      maxVersion: true,
      polyCount: true,
      vertexCount: true,
      hasTextures: true,
      isPbr: true,
      fileSizeBytes: true,
      downloadCount: true,
      viewCount: true,
      ratingAvg: true,
      ratingCount: true,
      publishedAt: true,
      isOfficial: true,
      author: { select: { name: true, slug: true, bio: true } },
      category: { select: { name: true, slug: true } },
      tags: { select: { tag: { select: { name: true, slug: true } } } },
      assets: {
        orderBy: { sortOrder: "asc" },
        select: { id: true, kind: true, storageKey: true, originalName: true },
      },
    },
  });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const model = await getModel((await params).slug);
  return { title: model?.title ?? "Model tapılmadı" };
}

export default async function ModelDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const model = await getModel(slug);
  if (!model || model.status !== "PUBLISHED") notFound();

  const user = await getCurrentUser();
  const owned = user ? await hasEntitlement(user.id, model.id) : false;

  // Baxış sayğacı (MVP-də sadə artırma; sonra unikal baxışa görə dəqiqləşdiriləcək)
  await prisma.model.update({
    where: { id: model.id },
    data: { viewCount: { increment: 1 } },
  });

  const [reviews, ownEntitlement, ownReview] = await Promise.all([
    prisma.review.findMany({
      where: { modelId: model.id },
      orderBy: { createdAt: "desc" },
      take: 30,
      select: {
        id: true,
        rating: true,
        comment: true,
        createdAt: true,
        user: { select: { name: true } },
      },
    }),
    // Rəy yazmaq üçün bir dəfə əldə etmək kifayətdir — müddəti bitmiş olsa belə.
    user
      ? prisma.entitlement.findFirst({ where: { userId: user.id, modelId: model.id }, select: { id: true } })
      : null,
    user
      ? prisma.review.findUnique({
          where: { userId_modelId: { userId: user.id, modelId: model.id } },
          select: { id: true, rating: true, comment: true },
        })
      : null,
  ]);

  const previewGlb = model.assets.find((a) => a.kind === "PREVIEW_GLB");
  const images = model.assets.filter((a) => a.kind === "IMAGE");
  const posterUrl = images[0] ? `/uploads/${images[0].storageKey}` : null;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      {/* Sol sütun — vizual */}
      <div className="space-y-4">
        {previewGlb ? (
          <ModelViewer
            src={`/uploads/${previewGlb.storageKey}`}
            poster={posterUrl}
            alt={`${model.title} 3D önizləmə`}
          />
        ) : posterUrl ? (
          <div className="relative aspect-4/3 overflow-hidden rounded-xl border border-border">
            <Image src={posterUrl} alt={model.title} fill className="object-cover" priority />
          </div>
        ) : (
          <div className="flex aspect-4/3 items-center justify-center rounded-xl border border-border bg-surface-2 text-sm text-muted">
            Önizləmə yoxdur
          </div>
        )}

        {images.length > 1 && (
          <div className="grid grid-cols-4 gap-3">
            {images.slice(1, 5).map((img) => (
              <div
                key={img.id}
                className="relative aspect-4/3 overflow-hidden rounded-lg border border-border"
              >
                <Image
                  src={`/uploads/${img.storageKey}`}
                  alt={model.title}
                  fill
                  sizes="25vw"
                  className="object-cover"
                />
              </div>
            ))}
          </div>
        )}

        <section>
          <h2 className="mb-2 text-sm font-semibold text-muted">Təsvir</h2>
          <p className="whitespace-pre-line text-sm leading-relaxed">
            {model.description || "Təsvir əlavə edilməyib."}
          </p>
        </section>

        {model.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {model.tags.map(({ tag }) => (
              <Link key={tag.slug} href={`/models?q=${tag.slug}`} className="badge hover:text-accent">
                #{tag.name}
              </Link>
            ))}
          </div>
        )}

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-muted">
            Rəylər {model.ratingCount > 0 && `(${model.ratingCount})`}
          </h2>

          {ownEntitlement && (
            <ReviewForm slug={model.slug} initial={ownReview ?? undefined} />
          )}

          {reviews.length === 0 ? (
            <p className="text-sm text-muted">Hələ rəy yazılmayıb.</p>
          ) : (
            <div className="card divide-y divide-border">
              {reviews.map((r) => (
                <div key={r.id} className="space-y-1 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <ReviewStars rating={r.rating} />
                      <span className="text-sm font-medium">{r.user.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted">
                        {r.createdAt.toLocaleDateString("az-AZ")}
                      </span>
                      {ownReview?.id === r.id && (
                        <form action={deleteReviewAction}>
                          <input type="hidden" name="slug" value={model.slug} />
                          <button type="submit" className="text-xs text-muted hover:text-danger">
                            Sil
                          </button>
                        </form>
                      )}
                    </div>
                  </div>
                  {r.comment && <p className="text-sm leading-relaxed">{r.comment}</p>}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Sağ sütun — alış və texniki məlumat */}
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-semibold leading-tight">{model.title}</h1>
          {model.ratingCount > 0 && (
            <div className="mt-1.5 flex items-center gap-1.5 text-sm">
              <ReviewStars rating={model.ratingAvg} size="md" />
              <span className="font-medium">{model.ratingAvg.toFixed(1)}</span>
              <span className="text-muted">
                ({model.ratingCount} rəy)
              </span>
            </div>
          )}
          {model.isOfficial ? (
            <p className="mt-1 text-sm text-accent">Arxvia rəsmi kolleksiyası</p>
          ) : model.author.slug ? (
            <Link
              href={`/artist/${model.author.slug}`}
              className="mt-1 inline-block text-sm text-muted hover:text-accent"
            >
              {model.author.name}
            </Link>
          ) : null}
        </div>

        <PurchaseBox
          slug={model.slug}
          modelId={model.id}
          creditCost={model.creditCost}
          owned={owned}
          isLoggedIn={user !== null}
          balance={user?.creditBalance ?? 0}
        />

        <dl className="card divide-y divide-border text-sm">
          <Spec label="Render" value={RENDERER_LABEL[model.renderer] ?? model.renderer} />
          <Spec label="Formatlar" value={model.formats.map((f) => f.toUpperCase()).join(", ") || "—"} />
          {model.maxVersion && <Spec label="3ds Max" value={model.maxVersion} />}
          {model.polyCount != null && <Spec label="Poliqon" value={formatPolys(model.polyCount)} />}
          {model.vertexCount != null && (
            <Spec label="Təpə (vertex)" value={formatCredits(model.vertexCount)} />
          )}
          <Spec label="Teksturalar" value={model.hasTextures ? "Var" : "Yoxdur"} />
          <Spec label="PBR" value={model.isPbr ? "Bəli" : "Xeyr"} />
          <Spec label="Fayl ölçüsü" value={formatBytes(model.fileSizeBytes)} />
          <Spec label="Kateqoriya" value={model.category?.name ?? "—"} />
          <Spec label="Endirilmə" value={String(model.downloadCount)} />
        </dl>

        <Link
          href={`/report?model=${model.slug}`}
          className="block text-center text-xs text-muted hover:text-danger"
        >
          Müəllif hüququ pozuntusu barədə məlumat ver
        </Link>
      </div>
    </div>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

function formatBytes(bytes: bigint): string {
  const n = Number(bytes);
  if (n === 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
