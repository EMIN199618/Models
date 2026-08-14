import Link from "next/link";
import { Suspense } from "react";

import { CatalogFilters } from "@/components/CatalogFilters";
import { ModelCard } from "@/components/ModelCard";
import { SearchBar } from "@/components/SearchBar";
import { SortSelect } from "@/components/SortSelect";
import { getCurrentUser } from "@/lib/auth";
import { getBreadcrumb, getFilterOptions, parseFilters, searchModels } from "@/lib/catalog";

export const metadata = { title: "Kataloq" };

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const filters = parseFilters(await searchParams);
  const user = await getCurrentUser();

  const [{ items, total, page, pageCount }, options, breadcrumb] = await Promise.all([
    searchModels(filters, user?.id),
    getFilterOptions(),
    getBreadcrumb(filters.category),
  ]);

  const heading =
    breadcrumb.length > 0
      ? breadcrumb[breadcrumb.length - 1].name
      : filters.q
        ? `"${filters.q}" üzrə nəticələr`
        : "Bütün modellər";

  return (
    <div className="grid gap-8 lg:grid-cols-[230px_1fr]">
      <Suspense fallback={<div className="text-sm text-muted">Filtrlər…</div>}>
        <CatalogFilters tree={options.tree} formats={options.formats} />
      </Suspense>

      <div className="min-w-0">
        <Suspense fallback={null}>
          <SearchBar className="mb-5 max-w-xl" />
        </Suspense>

        {breadcrumb.length > 0 && (
          <nav className="mb-2 flex items-center gap-1.5 text-xs text-muted">
            <Link href="/models" className="hover:text-accent">
              Kataloq
            </Link>
            {breadcrumb.map((crumb, i) => (
              <span key={crumb.slug} className="flex items-center gap-1.5">
                <span aria-hidden>/</span>
                {i === breadcrumb.length - 1 ? (
                  <span className="text-foreground">{crumb.name}</span>
                ) : (
                  <Link href={`/models?category=${crumb.slug}`} className="hover:text-accent">
                    {crumb.name}
                  </Link>
                )}
              </span>
            ))}
          </nav>
        )}

        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="text-xl font-semibold">
            {heading}
            <span className="ml-2 text-sm font-normal text-muted">{total} model</span>
          </h1>
          <Suspense fallback={null}>
            <SortSelect />
          </Suspense>
        </div>

        {items.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface p-10 text-center">
            <p className="text-sm text-muted">Bu filtrlərə uyğun model tapılmadı.</p>
            <Link href="/models" className="mt-3 inline-block text-sm text-accent hover:underline">
              Filtrləri sıfırla
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
            {items.map((m) => (
              <ModelCard key={m.slug} model={m} />
            ))}
          </div>
        )}

        {pageCount > 1 && <Pagination page={page} pageCount={pageCount} filters={filters} />}
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
