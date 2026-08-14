"use server";

import { revalidatePath } from "next/cache";

import { requireUser } from "@/lib/auth";
import { CreditError, purchaseModel } from "@/lib/credits";
import { prisma } from "@/lib/prisma";

export type PurchaseState = { ok?: boolean; error?: string } | undefined;

/**
 * Modeli Credit ilə "alır" — yəni endirmə hüququ yaradır.
 * Bütün balans məntiqi lib/credits.ts-dəki tranzaksiyadadır.
 */
export async function purchaseAction(
  _prev: PurchaseState,
  formData: FormData,
): Promise<PurchaseState> {
  const slug = String(formData.get("slug") ?? "");
  if (!slug) return { error: "Model tapılmadı" };

  let user;
  try {
    user = await requireUser();
  } catch {
    return { error: "Bu əməliyyat üçün daxil olmalısınız" };
  }

  const model = await prisma.model.findUnique({
    where: { slug },
    select: { id: true },
  });
  if (!model) return { error: "Model tapılmadı" };

  try {
    await purchaseModel({ userId: user.id, modelId: model.id });
  } catch (err) {
    if (err instanceof CreditError) return { error: err.message };
    throw err;
  }

  revalidatePath(`/models/${slug}`);
  return { ok: true };
}

export type FavoriteResult = { ok: boolean; favorited: boolean };

/** Seçilmişlərə əlavə edir və ya çıxarır. Nəticəni klient optimist UI üçün alır. */
export async function toggleFavoriteAction(slug: string): Promise<FavoriteResult> {
  let user;
  try {
    user = await requireUser();
  } catch {
    return { ok: false, favorited: false };
  }

  const model = await prisma.model.findUnique({
    where: { slug },
    select: { id: true },
  });
  if (!model) return { ok: false, favorited: false };

  const key = { userId_modelId: { userId: user.id, modelId: model.id } };
  const existing = await prisma.favorite.findUnique({ where: key });

  if (existing) {
    await prisma.favorite.delete({ where: key });
  } else {
    await prisma.favorite.create({ data: { userId: user.id, modelId: model.id } });
  }

  revalidatePath("/favorites");
  return { ok: true, favorited: !existing };
}
