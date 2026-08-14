import { notFound } from "next/navigation";

import { ModelCard, type ModelCardData } from "@/components/ModelCard";
import { prisma } from "@/lib/prisma";

async function getArtist(slug: string) {
  return prisma.user.findUnique({
    where: { slug },
    select: {
      id: true,
      name: true,
      bio: true,
      country: true,
      createdAt: true,
      models: {
        where: { status: "PUBLISHED" },
        orderBy: { publishedAt: "desc" },
        select: {
          slug: true,
          title: true,
          creditCost: true,
          renderer: true,
          formats: true,
          polyCount: true,
          downloadCount: true,
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
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const artist = await getArtist((await params).slug);
  return { title: artist?.name ?? "Artist tapılmadı" };
}

export default async function ArtistPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const artist = await getArtist((await params).slug);
  if (!artist) notFound();

  const totalDownloads = artist.models.reduce((sum, m) => sum + m.downloadCount, 0);

  const cards: ModelCardData[] = artist.models.map((m) => ({
    slug: m.slug,
    title: m.title,
    creditCost: m.creditCost,
    renderer: m.renderer,
    formats: m.formats,
    polyCount: m.polyCount,
    downloadCount: m.downloadCount,
    isOfficial: m.isOfficial,
    thumbnailUrl: m.assets[0] ? `/uploads/${m.assets[0].storageKey}` : null,
    author: m.author,
  }));

  return (
    <div className="space-y-8">
      <header className="card flex flex-wrap items-center gap-6 p-6">
        <div className="flex size-16 items-center justify-center rounded-full bg-accent/20 text-2xl font-semibold text-accent">
          {artist.name.charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold">{artist.name}</h1>
          {artist.bio && <p className="mt-1 max-w-2xl text-sm text-muted">{artist.bio}</p>}
          <p className="mt-2 text-xs text-muted">
            {artist.country ? `${artist.country} · ` : ""}
            {artist.createdAt.getFullYear()}-dən bəri
          </p>
        </div>
        <dl className="flex gap-8 text-center">
          <div>
            <dt className="text-xs text-muted">Model</dt>
            <dd className="text-xl font-semibold">{artist.models.length}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Endirilmə</dt>
            <dd className="text-xl font-semibold">{totalDownloads}</dd>
          </div>
        </dl>
      </header>

      {cards.length === 0 ? (
        <p className="card p-10 text-center text-sm text-muted">
          Bu artistin hələ dərc olunmuş modeli yoxdur.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {cards.map((m) => (
            <ModelCard key={m.slug} model={m} />
          ))}
        </div>
      )}
    </div>
  );
}
