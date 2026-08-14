import "server-only";

import { prisma } from "@/lib/prisma";
import type { CreditReason } from "@/generated/prisma/enums";

export class CreditError extends Error {
  constructor(
    message: string,
    readonly code: "INSUFFICIENT" | "NOT_FOUND" | "NOT_AVAILABLE",
  ) {
    super(message);
  }
}

/**
 * İstifadəçiyə Credit əlavə edir (abunə, admin, referral, bonus).
 * Balans və jurnal (ledger) HƏMİŞƏ eyni tranzaksiyada yenilənir.
 */
export async function grantCredits(params: {
  userId: string;
  amount: number;
  reason: CreditReason;
  note?: string;
}): Promise<number> {
  const { userId, amount, reason, note } = params;
  if (amount <= 0) throw new CreditError("Məbləğ müsbət olmalıdır", "NOT_AVAILABLE");

  return prisma.$transaction(async (tx) => {
    const user = await tx.user.update({
      where: { id: userId },
      data: { creditBalance: { increment: amount } },
      select: { creditBalance: true },
    });

    await tx.creditTransaction.create({
      data: {
        userId,
        amount,
        reason,
        balanceAfter: user.creditBalance,
        note,
      },
    });

    return user.creditBalance;
  });
}

/**
 * Modelin endirilmə hüququnu alır.
 *
 * Qaydalar:
 *  - Yalnız PUBLISHED model alına bilər.
 *  - Artist öz modelinə Credit xərcləmir.
 *  - Əvvəl alınıbsa, təkrar Credit tutulmur (idempotent).
 *  - Balans çatmırsa, əməliyyat tam geri qaytarılır.
 */
export async function purchaseModel(params: {
  userId: string;
  modelId: string;
}): Promise<{ entitlementId: string; creditsSpent: number; alreadyOwned: boolean }> {
  const { userId, modelId } = params;

  return prisma.$transaction(async (tx) => {
    const existing = await tx.entitlement.findUnique({
      where: { userId_modelId: { userId, modelId } },
      select: { id: true, creditsSpent: true },
    });
    if (existing) {
      return {
        entitlementId: existing.id,
        creditsSpent: existing.creditsSpent,
        alreadyOwned: true,
      };
    }

    const model = await tx.model.findUnique({
      where: { id: modelId },
      select: { id: true, status: true, creditCost: true, authorId: true },
    });
    if (!model) throw new CreditError("Model tapılmadı", "NOT_FOUND");
    if (model.status !== "PUBLISHED") {
      throw new CreditError("Bu model əlçatan deyil", "NOT_AVAILABLE");
    }

    // Müəllif öz modelini pulsuz endirir.
    const cost = model.authorId === userId ? 0 : model.creditCost;

    if (cost > 0) {
      const user = await tx.user.findUnique({
        where: { id: userId },
        select: { creditBalance: true },
      });
      if (!user) throw new CreditError("İstifadəçi tapılmadı", "NOT_FOUND");
      if (user.creditBalance < cost) {
        throw new CreditError("Credit balansınız kifayət etmir", "INSUFFICIENT");
      }

      const updated = await tx.user.update({
        where: { id: userId },
        data: { creditBalance: { decrement: cost } },
        select: { creditBalance: true },
      });

      await tx.creditTransaction.create({
        data: {
          userId,
          amount: -cost,
          reason: "DOWNLOAD_SPEND",
          balanceAfter: updated.creditBalance,
          modelId,
        },
      });
    }

    const entitlement = await tx.entitlement.create({
      data: { userId, modelId, creditsSpent: cost },
      select: { id: true },
    });

    await tx.model.update({
      where: { id: modelId },
      data: { downloadCount: { increment: 1 } },
    });

    return { entitlementId: entitlement.id, creditsSpent: cost, alreadyOwned: false };
  });
}

/** İstifadəçinin modeli endirmə hüququ varmı? */
export async function hasEntitlement(userId: string, modelId: string): Promise<boolean> {
  const found = await prisma.entitlement.findUnique({
    where: { userId_modelId: { userId, modelId } },
    select: { id: true },
  });
  return found !== null;
}
