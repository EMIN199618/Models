"use server";

import { revalidatePath } from "next/cache";

import { requireUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { findPackage } from "@/lib/pricing";

export type OrderState = { ok?: boolean; error?: string; orderId?: string } | undefined;

/**
 * Credit paketi sifarişi yaradır.
 *
 * Ödəniş şlüzü hələ yoxdur: sifariş PENDING statusunda qalır, admin ödənişi
 * təsdiqləyəndə Credit köçürülür. Şlüz qoşulanda yalnız bu addım
 * avtomatlaşacaq — qalan məntiq dəyişməyəcək.
 */
export async function createOrderAction(
  _prev: OrderState,
  formData: FormData,
): Promise<OrderState> {
  let user;
  try {
    user = await requireUser();
  } catch {
    return { error: "Paket almaq üçün daxil olmalısınız" };
  }

  const packageId = String(formData.get("packageId") ?? "");
  const pkg = findPackage(packageId);
  if (!pkg) return { error: "Paket tapılmadı" };

  // Eyni paket üzrə açıq sifariş varsa, təkrar yaradılmır.
  const existing = await prisma.creditOrder.findFirst({
    where: { userId: user.id, packageId: pkg.id, status: "PENDING" },
    select: { id: true },
  });
  if (existing) {
    return { ok: true, orderId: existing.id };
  }

  const order = await prisma.creditOrder.create({
    data: {
      userId: user.id,
      packageId: pkg.id,
      credits: pkg.credits,
      priceMinor: pkg.priceMinor,
      currency: pkg.currency,
    },
    select: { id: true },
  });

  revalidatePath("/pricing");
  revalidatePath("/account");
  return { ok: true, orderId: order.id };
}

export async function cancelOrderAction(formData: FormData): Promise<void> {
  const user = await requireUser();
  const orderId = String(formData.get("orderId") ?? "");
  if (!orderId) return;

  // Yalnız öz gözləyən sifarişini ləğv edə bilər.
  await prisma.creditOrder.updateMany({
    where: { id: orderId, userId: user.id, status: "PENDING" },
    data: { status: "CANCELED" },
  });

  revalidatePath("/account");
  revalidatePath("/pricing");
}
