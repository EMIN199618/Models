import Link from "next/link";
import { redirect } from "next/navigation";

import { ModelCard, type ModelCardData } from "@/components/ModelCard";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export const metadata = { title: "Seçilmişlər" };

export default async function FavoritesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const favorites = await prisma.favorite.findMany({
    where: { userId: user.id, model: { status: "PUBLISHED" } },
    orderBy: { createdAt: "desc" },
    select: {
      model: {
        select: {
          slug: true,
          title: true,
          creditCost: true,
          renderer: true,
          formats: true,
          polyCount: true,
          downloadCount: true,
          ratingAvg: true,
          ratingCount: true,
          isOfficial: true,
          author: { select: { name: true, slug: true } },
          assets: {
            where: { kind: "IMAGE" },
            orderBy: { sortOrder: "asc" },
            take: 1,
            select: { storageKey: true },
          },
        },
      },
    },
  });

  const cards: ModelCardData[] = favorites.map(({ model }) => ({
    slug: model.slug,
    title: model.title,
    creditCost: model.creditCost,
    renderer: model.renderer,
    formats: model.formats,
    polyCount: model.polyCount,
    downloadCount: model.downloadCount,
    ratingAvg: model.ratingAvg,
    ratingCount: model.ratingCount,
    isOfficial: model.isOfficial,
    thumbnailUrl: model.assets[0] ? `/uploads/${model.assets[0].storageKey}` : null,
    author: model.author,
    isFavorite: true,
  }));

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold">
        Seçilmişlər
        <span className="ml-2 text-sm font-normal text-muted">{cards.length} model</span>
      </h1>

      {cards.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-10 text-center">
          <p className="text-sm text-muted">
            Hələ heç bir modeli seçilmişlərə əlavə etməmisiniz.
          </p>
          <p className="mt-1 text-xs text-muted">
            Kataloqda model kartının üzərinə gələndə görünən ürək ikonuna basın.
          </p>
          <Link href="/models" className="mt-3 inline-block text-sm text-accent hover:underline">
            Kataloqa keç
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
          {cards.map((m) => (
            <ModelCard key={m.slug} model={m} />
          ))}
        </div>
      )}
    </div>
  );
}
