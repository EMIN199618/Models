"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { requireRole } from "@/lib/auth";
import { grantCredits } from "@/lib/credits";
import { prisma } from "@/lib/prisma";

/** Modeli təsdiqləyib kataloqa buraxır. */
export async function approveModelAction(formData: FormData): Promise<void> {
  const admin = await requireRole("ADMIN");
  const modelId = String(formData.get("modelId") ?? "");
  if (!modelId) return;

  await prisma.model.update({
    where: { id: modelId },
    data: {
      status: "PUBLISHED",
      publishedAt: new Date(),
      reviewedAt: new Date(),
      reviewedById: admin.id,
      rejectionReason: null,
    },
  });

  revalidatePath("/admin");
  revalidatePath("/models");
}

const rejectSchema = z.object({
  modelId: z.string().min(1),
  reason: z.string().trim().min(3, "Səbəb qeyd edilməlidir").max(500),
});

export async function rejectModelAction(formData: FormData): Promise<void> {
  const admin = await requireRole("ADMIN");
  const parsed = rejectSchema.safeParse({
    modelId: formData.get("modelId"),
    reason: formData.get("reason"),
  });
  if (!parsed.success) return;

  await prisma.model.update({
    where: { id: parsed.data.modelId },
    data: {
      status: "REJECTED",
      reviewedAt: new Date(),
      reviewedById: admin.id,
      rejectionReason: parsed.data.reason,
    },
  });

  revalidatePath("/admin");
}

/** Dərc olunmuş modeli arxivə salır (məs. müəllif hüququ şikayəti). */
export async function archiveModelAction(formData: FormData): Promise<void> {
  await requireRole("ADMIN");
  const modelId = String(formData.get("modelId") ?? "");
  if (!modelId) return;

  await prisma.model.update({
    where: { id: modelId },
    data: { status: "ARCHIVED" },
  });

  revalidatePath("/admin");
  revalidatePath("/models");
}

const grantSchema = z.object({
  email: z.string().trim().toLowerCase().email(),
  amount: z.coerce.number().int().min(1).max(10000),
});

/**
 * Admin tərəfindən Credit verilməsi.
 * Ödəniş şlüzü qoşulanadək abunə/Credit satışının yerini bu tutur.
 */
export async function grantCreditsAction(formData: FormData): Promise<void> {
  await requireRole("ADMIN");
  const parsed = grantSchema.safeParse({
    email: formData.get("email"),
    amount: formData.get("amount"),
  });
  if (!parsed.success) return;

  const user = await prisma.user.findUnique({
    where: { email: parsed.data.email },
    select: { id: true },
  });
  if (!user) return;

  await grantCredits({
    userId: user.id,
    amount: parsed.data.amount,
    reason: "ADMIN_GRANT",
    note: "Admin tərəfindən əlavə edilib",
  });

  revalidatePath("/admin");
}

/**
 * Credit paketi sifarişini "ödənildi" işarələyir və Credit-i köçürür.
 *
 * Ödəniş şlüzü qoşulanda məhz bu funksiya şlüzün callback-indən çağırılacaq —
 * qalan məntiq dəyişməyəcək.
 */
export async function markOrderPaidAction(formData: FormData): Promise<void> {
  await requireRole("ADMIN");
  const orderId = String(formData.get("orderId") ?? "");
  if (!orderId) return;

  await prisma.$transaction(async (tx) => {
    // Yalnız PENDING → PAID keçidi. Təkrar təsdiq Credit-i ikiqat verməsin.
    const updated = await tx.creditOrder.updateMany({
      where: { id: orderId, status: "PENDING" },
      data: { status: "PAID", paidAt: new Date() },
    });
    if (updated.count === 0) return;

    const order = await tx.creditOrder.findUniqueOrThrow({
      where: { id: orderId },
      select: { userId: true, credits: true, packageId: true },
    });

    const user = await tx.user.update({
      where: { id: order.userId },
      data: { creditBalance: { increment: order.credits } },
      select: { creditBalance: true },
    });

    await tx.creditTransaction.create({
      data: {
        userId: order.userId,
        amount: order.credits,
        reason: "CREDIT_PACKAGE",
        balanceAfter: user.creditBalance,
        note: `Paket: ${order.packageId}`,
      },
    });
  });

  revalidatePath("/admin");
  revalidatePath("/account");
}

export async function cancelOrderAdminAction(formData: FormData): Promise<void> {
  await requireRole("ADMIN");
  const orderId = String(formData.get("orderId") ?? "");
  if (!orderId) return;

  await prisma.creditOrder.updateMany({
    where: { id: orderId, status: "PENDING" },
    data: { status: "CANCELED" },
  });

  revalidatePath("/admin");
}

export async function resolveReportAction(formData: FormData): Promise<void> {
  await requireRole("ADMIN");
  const reportId = String(formData.get("reportId") ?? "");
  const status = String(formData.get("status") ?? "");
  if (!reportId || (status !== "RESOLVED" && status !== "DISMISSED")) return;

  await prisma.report.update({
    where: { id: reportId },
    data: { status },
  });

  revalidatePath("/admin");
}
