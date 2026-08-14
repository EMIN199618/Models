import Link from "next/link";
import { Suspense } from "react";

import { ModelCard } from "@/components/ModelCard";
import { NewModelsMarquee } from "@/components/NewModelsMarquee";
import { SearchBar } from "@/components/SearchBar";
import { getCurrentUser } from "@/lib/auth";
import { getCategoryTree, searchModels } from "@/lib/catalog";
import { prisma } from "@/lib/prisma";

export default async function HomePage() {
  const user = await getCurrentUser();

  const [newest, popular, tree, stats] = await Promise.all([
    searchModels({ sort: "new", page: 1 }, user?.id),
    searchModels({ sort: "popular", page: 1 }, user?.id),
    getCategoryTree(),
    Promise.all([
      prisma.model.count({ where: { status: "PUBLISHED" } }),
      prisma.user.count({ where: { role: "ARTIST" } }),
    ]),
  ]);

  const [modelCount, artistCount] = stats;

  return (
    <div className="space-y-14">
      <section className="pt-6 text-center">
        <h1 className="mx-auto max-w-3xl text-balance text-4xl font-semibold leading-tight sm:text-5xl">
          3ds Max, Corona və V-Ray üçün{" "}
          <span className="text-accent">peşəkar 3D modellər</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-balance text-muted">
          İnteryer dizaynerlər, memarlar və vizualizasiya studiyaları üçün kataloq.
          Təbii dildə axtar, brauzerdə fırlat, dərhal endir.
        </p>

        <div className="mx-auto mt-7 max-w-xl">
          <Suspense fallback={null}>
            <SearchBar />
          </Suspense>
        </div>

        <div className="mt-6 flex items-center justify-center gap-6 text-sm text-muted">
          <span>
            <strong className="text-foreground">{modelCount}</strong> model
          </span>
          <span>
            <strong className="text-foreground">{artistCount}</strong> artist
          </span>
        </div>
      </section>

      {/* Yeni modellər — sağdan sola fasiləsiz lent */}
      <NewModelsMarquee models={newest.items.slice(0, 14)} />

      <section>
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Kateqoriyalar</h2>
          <Link href="/models" className="text-sm text-accent hover:underline">
            Kataloqa keç →
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {tree.map((c) => (
            <Link
              key={c.slug}
              href={`/models?category=${c.slug}`}
              className="rounded-lg border border-border bg-surface px-4 py-3 transition-colors hover:border-accent/60"
            >
              <span className="block truncate text-sm font-medium">{c.name}</span>
              <span className="text-xs text-muted">{c.count} model</span>
            </Link>
          ))}
        </div>
      </section>

      <ModelSection
        title="Ən populyar"
        href="/models?sort=popular"
        models={popular.items.slice(0, 10)}
      />


      <section className="card p-8 text-center">
        <h2 className="text-xl font-semibold">Artistsiniz?</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm text-muted">
          Model yükləmək tamamilə pulsuzdur. Öz profilinizi, portfolionuzu və
          endirilmə statistikanızı idarə edin.
        </p>
        <Link href="/register" className="btn-primary mt-5">
          Artist kimi qeydiyyatdan keç
        </Link>
      </section>
    </div>
  );
}

function ModelSection({
  title,
  href,
  models,
}: {
  title: string;
  href: string;
  models: Awaited<ReturnType<typeof searchModels>>["items"];
}) {
  if (models.length === 0) return null;

  return (
    <section>
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Link href={href} className="text-sm text-accent hover:underline">
          Hamısına bax →
        </Link>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {models.map((m) => (
          <ModelCard key={m.slug} model={m} />
        ))}
      </div>
    </section>
  );
}
