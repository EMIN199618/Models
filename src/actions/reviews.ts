"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { requireUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import type { Prisma } from "@/generated/prisma/client";

export type ReviewState = { ok?: boolean; error?: string } | undefined;

const reviewSchema = z.object({
  slug: z.string().min(1),
  rating: z.coerce.number().int().min(1).max(5),
  comment: z.string().trim().max(1000).optional().default(""),
});

/** Model reytinq xülasəsini (ratingAvg/ratingCount) Review cədvəlindən yenidən hesablayır. */
async function recomputeRating(tx: Prisma.TransactionClient, modelId: string): Promise<void> {
  const agg = await tx.review.aggregate({
    where: { modelId },
    _avg: { rating: true },
    _count: { _all: true },
  });

  await tx.model.update({
    where: { id: modelId },
    data: {
      ratingAvg: agg._avg.rating ?? 0,
      ratingCount: agg._count._all,
    },
  });
}

/**
 * Rəy yaradır və ya (istifadəçinin həmin model üçün) mövcud rəyini yeniləyir.
 *
 * Yalnız modeli əldə etmiş (heç olmasa bir dəfə alışı olan) istifadəçi rəy
 * yaza bilər — bax Entitlement. Müddəti keçmiş hüquq kifayətdir, çünki rəy
 * faylı yenidən endirməyi yox, təcrübəni qiymətləndirir.
 */
export async function submitReviewAction(
  _prev: ReviewState,
  formData: FormData,
): Promise<ReviewState> {
  const parsed = reviewSchema.safeParse({
    slug: formData.get("slug"),
    rating: formData.get("rating"),
    comment: formData.get("comment"),
  });
  if (!parsed.success) return { error: "Reytinq 1–5 arasında olmalıdır" };

  let user;
  try {
    user = await requireUser();
  } catch {
    return { error: "Rəy yazmaq üçün daxil olmalısınız" };
  }

  const model = await prisma.model.findUnique({
    where: { slug: parsed.data.slug },
    select: { id: true },
  });
  if (!model) return { error: "Model tapılmadı" };

  const owns = await prisma.entitlement.findFirst({
    where: { userId: user.id, modelId: model.id },
    select: { id: true },
  });
  if (!owns) return { error: "Rəy yalnız əldə etdiyiniz modellər üçün mümkündür" };

  await prisma.$transaction(async (tx) => {
    await tx.review.upsert({
      where: { userId_modelId: { userId: user.id, modelId: model.id } },
      create: {
        userId: user.id,
        modelId: model.id,
        rating: parsed.data.rating,
        comment: parsed.data.comment,
      },
      update: {
        rating: parsed.data.rating,
        comment: parsed.data.comment,
      },
    });

    await recomputeRating(tx, model.id);
  });

  revalidatePath(`/models/${parsed.data.slug}`);
  return { ok: true };
}

export async function deleteReviewAction(formData: FormData): Promise<void> {
  const user = await requireUser();
  const slug = String(formData.get("slug") ?? "");
  if (!slug) return;

  const model = await prisma.model.findUnique({
    where: { slug },
    select: { id: true },
  });
  if (!model) return;

  await prisma.$transaction(async (tx) => {
    const deleted = await tx.review.deleteMany({
      where: { userId: user.id, modelId: model.id },
    });
    if (deleted.count > 0) await recomputeRating(tx, model.id);
  });

  revalidatePath(`/models/${slug}`);
}
