import "server-only";

import { prisma } from "@/lib/prisma";
import type { Prisma } from "@/generated/prisma/client";
import type { ModelCardData } from "@/components/ModelCard";

export const PAGE_SIZE = 24;

export type CatalogFilters = {
  q?: string;
  category?: string;
  renderer?: string;
  format?: string;
  free?: boolean;
  sort?: "new" | "popular" | "cheap";
  page?: number;
};

/** searchParams-dan təhlükəsiz filtr obyekti çıxarır. */
export function parseFilters(
  params: Record<string, string | string[] | undefined>,
): CatalogFilters {
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
  const sort = one(params.sort);
  const page = Number.parseInt(one(params.page) ?? "1", 10);

  return {
    q: one(params.q)?.trim() || undefined,
    category: one(params.category) || undefined,
    renderer: one(params.renderer) || undefined,
    format: one(params.format)?.toLowerCase() || undefined,
    free: one(params.free) === "1",
    sort: sort === "popular" || sort === "cheap" ? sort : "new",
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function buildWhere(f: CatalogFilters): Prisma.ModelWhereInput {
  const where: Prisma.ModelWhereInput = { status: "PUBLISHED" };

  if (f.q) {
    // MVP axtarışı: başlıq/təsvir/tag üzrə. Semantik "AI axtarış" növbəti
    // mərhələdə pgvector embedding-ləri ilə bunun üzərinə əlavə olunacaq.
    where.OR = [
      { title: { contains: f.q, mode: "insensitive" } },
      { description: { contains: f.q, mode: "insensitive" } },
      { tags: { some: { tag: { name: { contains: f.q, mode: "insensitive" } } } } },
    ];
  }
  if (f.category) {
    // Valideyn kateqoriya seçiləndə onun bütün alt kateqoriyaları da daxildir.
    where.category = {
      OR: [{ slug: f.category }, { parent: { slug: f.category } }],
    };
  }
  if (f.renderer && f.renderer !== "ALL") {
    where.renderer = f.renderer as Prisma.ModelWhereInput["renderer"];
  }
  if (f.format) where.formats = { has: f.format };
  if (f.free) where.creditCost = 0;

  return where;
}

function buildOrderBy(f: CatalogFilters): Prisma.ModelOrderByWithRelationInput[] {
  switch (f.sort) {
    case "popular":
      return [{ downloadCount: "desc" }, { publishedAt: "desc" }];
    case "cheap":
      return [{ creditCost: "asc" }, { publishedAt: "desc" }];
    default:
      return [{ publishedAt: "desc" }];
  }
}

const CARD_SELECT = {
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
    where: { kind: "IMAGE" as const },
    orderBy: { sortOrder: "asc" as const },
    take: 1,
    select: { storageKey: true },
  },
} satisfies Prisma.ModelSelect;

type RawCard = Prisma.ModelGetPayload<{ select: typeof CARD_SELECT }>;

function toCard(m: RawCard): ModelCardData {
  return {
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
  };
}

export async function searchModels(
  f: CatalogFilters,
  userId?: string,
): Promise<{
  items: ModelCardData[];
  total: number;
  page: number;
  pageCount: number;
}> {
  const where = buildWhere(f);
  const page = f.page ?? 1;

  const [rows, total] = await Promise.all([
    prisma.model.findMany({
      where,
      orderBy: buildOrderBy(f),
      skip: (page - 1) * PAGE_SIZE,
      take: PAGE_SIZE,
      select: { ...CARD_SELECT, id: true },
    }),
    prisma.model.count({ where }),
  ]);

  const items = rows.map(toCard);

  // Girişli istifadəçi üçün seçilmişlər — tək sorğu ilə.
  if (userId && rows.length > 0) {
    const favorites = await prisma.favorite.findMany({
      where: { userId, modelId: { in: rows.map((r) => r.id) } },
      select: { modelId: true },
    });
    const favSet = new Set(favorites.map((f) => f.modelId));
    rows.forEach((row, i) => {
      items[i].isFavorite = favSet.has(row.id);
    });
  }

  return {
    items,
    total,
    page,
    pageCount: Math.max(1, Math.ceil(total / PAGE_SIZE)),
  };
}

export type CategoryTreeNode = {
  slug: string;
  name: string;
  count: number;
  children: { slug: string; name: string; count: number }[];
};

/**
 * Kateqoriya ağacı + hər düyündə model sayı.
 * Valideynin sayı öz alt kateqoriyalarının cəmidir.
 */
export async function getCategoryTree(): Promise<CategoryTreeNode[]> {
  const [categories, counts] = await Promise.all([
    prisma.category.findMany({
      orderBy: [{ sortOrder: "asc" }, { name: "asc" }],
      select: { id: true, slug: true, name: true, parentId: true },
    }),
    prisma.model.groupBy({
      by: ["categoryId"],
      where: { status: "PUBLISHED" },
      _count: { _all: true },
    }),
  ]);

  const countById = new Map(
    counts
      .filter((c) => c.categoryId !== null)
      .map((c) => [c.categoryId as string, c._count._all]),
  );

  const parents = categories.filter((c) => c.parentId === null);

  return parents.map((parent) => {
    const children = categories
      .filter((c) => c.parentId === parent.id)
      .map((c) => ({ slug: c.slug, name: c.name, count: countById.get(c.id) ?? 0 }));

    // Valideynin öz birbaşa modelləri (varsa) + alt kateqoriyaların cəmi
    const own = countById.get(parent.id) ?? 0;
    const total = own + children.reduce((sum, c) => sum + c.count, 0);

    return { slug: parent.slug, name: parent.name, count: total, children };
  });
}

export async function getFilterOptions() {
  const [tree, formatRows] = await Promise.all([
    getCategoryTree(),
    prisma.model.findMany({
      where: { status: "PUBLISHED" },
      select: { formats: true },
    }),
  ]);

  const formats = [...new Set(formatRows.flatMap((r) => r.formats))].sort();
  return { tree, formats };
}

/** Seçilmiş kateqoriya üçün "Kataloq / Mebel / Divan" naviqasiya zənciri. */
export async function getBreadcrumb(
  slug: string | undefined,
): Promise<{ slug: string; name: string }[]> {
  if (!slug) return [];

  const category = await prisma.category.findUnique({
    where: { slug },
    select: {
      slug: true,
      name: true,
      parent: { select: { slug: true, name: true } },
    },
  });
  if (!category) return [];

  return category.parent
    ? [
        { slug: category.parent.slug, name: category.parent.name },
        { slug: category.slug, name: category.name },
      ]
    : [{ slug: category.slug, name: category.name }];
}
