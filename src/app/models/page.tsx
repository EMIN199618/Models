import Link from "next/link";
import { Suspense } from "react";

import { CatalogFilters } from "@/components/CatalogFilters";
import { ModelCard } from "@/components/ModelCard";
import { SearchBar } from "@/components/SearchBar";
import { getFilterOptions, parseFilters, searchModels } from "@/lib/catalog";

export const metadata = { title: "Kataloq" };

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const filters = parseFilters(await searchParams);
  const [{ items, total, page, pageCount }, options] = await Promise.all([
    searchModels(filters),
    getFilterOptions(),
  ]);

  return (
    <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
      <Suspense fallback={<div className="text-sm text-muted">Filtrlər…</div>}>
        <CatalogFilters categories={options.categories} formats={options.formats} />
      </Suspense>

      <div>
        <Suspense fallback={null}>
          <SearchBar className="mb-5 max-w-xl" />
        </Suspense>

        <div className="mb-4 flex items-baseline justify-between">
          <h1 className="text-xl font-semibold">
            {filters.q ? `"${filters.q}" üzrə nəticələr` : "Bütün modellər"}
          </h1>
          <span className="text-sm text-muted">{total} model</span>
        </div>

        {items.length === 0 ? (
          <div className="card p-10 text-center">
            <p className="text-sm text-muted">
              Bu filtrlərə uyğun model tapılmadı.
            </p>
            <Link href="/models" className="mt-3 inline-block text-sm text-accent hover:underline">
              Filtrləri sıfırla
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {items.map((m) => (
              <ModelCard key={m.slug} model={m} />
            ))}
          </div>
        )}

        {pageCount > 1 && (
          <Pagination page={page} pageCount={pageCount} filters={filters} />
        )}
      </div>
    </div>
  );
}

function Pagination({
  page,
  pageCount,
  filters,
}: {
  page: number;
  pageCount: number;
  filters: ReturnType<typeof parseFilters>;
}) {
  const href = (p: number) => {
    const params = new URLSearchParams();
    if (filters.q) params.set("q", filters.q);
    if (filters.category) params.set("category", filters.category);
    if (filters.renderer) params.set("renderer", filters.renderer);
    if (filters.format) params.set("format", filters.format);
    if (filters.free) params.set("free", "1");
    if (filters.sort && filters.sort !== "new") params.set("sort", filters.sort);
    params.set("page", String(p));
    return `/models?${params.toString()}`;
  };

  return (
    <nav className="mt-8 flex items-center justify-center gap-2">
      {page > 1 && (
        <Link href={href(page - 1)} className="btn-ghost">
          Əvvəlki
        </Link>
      )}
      <span className="px-3 text-sm text-muted">
        {page} / {pageCount}
      </span>
      {page < pageCount && (
        <Link href={href(page + 1)} className="btn-ghost">
          Növbəti
        </Link>
      )}
    </nav>
  );
}
