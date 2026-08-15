import "server-only";

import { prisma } from "@/lib/prisma";
import {
  artistShareOf,
  CREDIT_VALIDITY_DAYS,
  DOWNLOAD_WINDOW_HOURS,
} from "@/lib/pricing";
import type { CreditReason } from "@/generated/prisma/enums";
import type { Prisma } from "@/generated/prisma/client";

export class CreditError extends Error {
  constructor(
    message: string,
    readonly code: "INSUFFICIENT" | "NOT_FOUND" | "NOT_AVAILABLE",
  ) {
    super(message);
  }
}

/** Prisma tranzaksiya klienti — həm tx, həm adi client qəbul edən köməkçilər üçün. */
type Tx = Prisma.TransactionClient | typeof prisma;

// ---------------------------------------------------------------------------
// Balans
// ---------------------------------------------------------------------------

/**
 * Etibarlı balans — yalnız müddəti bitməmiş lotların qalıqları.
 *
 * Credit-lər lot şəklində verilir (hər verilişin öz bitmə tarixi var).
 * Müddəti keçmiş lotlar sadəcə hesaba daxil edilmir — ayrıca "yandırma"
 * prosesi lazım deyil.
 */
export async function getValidBalance(userId: string, client: Tx = prisma): Promise<number> {
  const result = await client.creditTransaction.aggregate({
    where: {
      userId,
      amount: { gt: 0 },
      remaining: { gt: 0 },
      OR: [{ expiresAt: null }, { expiresAt: { gt: new Date() } }],
    },
    _sum: { remaining: true },
  });
  return result._sum.remaining ?? 0;
}

/**
 * Lotlardan Credit xərcləyir — müddəti ən tez bitəndən başlayaraq.
 * Balans çatmasa xəta atır (tranzaksiya geri qaytarılır).
 */
async function consumeFromLots(
  tx: Prisma.TransactionClient,
  userId: string,
  amount: number,
): Promise<void> {
  const lots = await tx.creditTransaction.findMany({
    where: {
      userId,
      amount: { gt: 0 },
      remaining: { gt: 0 },
      OR: [{ expiresAt: null }, { expiresAt: { gt: new Date() } }],
    },
    orderBy: [{ expiresAt: "asc" }, { createdAt: "asc" }],
    select: { id: true, remaining: true },
  });

  const available = lots.reduce((sum, lot) => sum + lot.remaining, 0);
  if (available < amount) {
    throw new CreditError("Credit balansınız kifayət etmir", "INSUFFICIENT");
  }

  let left = amount;
  for (const lot of lots) {
    if (left === 0) break;
    const take = Math.min(lot.remaining, left);
    await tx.creditTransaction.update({
      where: { id: lot.id },
      data: { remaining: { decrement: take } },
    });
    left -= take;
  }
}

// ---------------------------------------------------------------------------
// Credit vermə
// ---------------------------------------------------------------------------

/**
 * İstifadəçiyə Credit əlavə edir (paket, admin, referral, bonus).
 *
 * Yeni lot yaradılır: `remaining` = məbləğ, `expiresAt` = indi + müddət.
 * Balans və jurnal HƏMİŞƏ eyni tranzaksiyada yenilənir.
 */
export async function grantCredits(params: {
  userId: string;
  amount: number;
  reason: CreditReason;
  note?: string;
  /** null verilsə, Credit-lərin müddəti bitmir (məs. kompensasiya) */
  validityDays?: number | null;
}): Promise<number> {
  const { userId, amount, reason, note } = params;
  if (amount <= 0) throw new CreditError("Məbləğ müsbət olmalıdır", "NOT_AVAILABLE");

  const days = params.validityDays === undefined ? CREDIT_VALIDITY_DAYS : params.validityDays;
  const expiresAt =
    days === null ? null : new Date(Date.now() + days * 24 * 60 * 60 * 1000);

  return prisma.$transaction(async (tx) => {
    const balance = (await getValidBalance(userId, tx)) + amount;

    await tx.creditTransaction.create({
      data: {
        userId,
        amount,
        reason,
        balanceAfter: balance,
        note,
        expiresAt,
        remaining: amount,
      },
    });

    await tx.user.update({
      where: { id: userId },
      data: { creditBalance: balance },
    });

    return balance;
  });
}

// ---------------------------------------------------------------------------
// Alış
// ---------------------------------------------------------------------------

/**
 * Modelin endirilmə hüququnu alır.
 *
 * Qaydalar:
 *  - Yalnız PUBLISHED model alına bilər.
 *  - Artist öz modelinə Credit xərcləmir.
 *  - Hüquq MÜDDƏTLİDİR (DOWNLOAD_WINDOW_HOURS). Müddət bitəndən sonra
 *    modeli yenidən almaq lazımdır — təkrar endirmə pulsuz deyil.
 *  - Aktiv hüquq varsa, təkrar Credit tutulmur (eyni pəncərə davam edir).
 *  - Balans çatmırsa, əməliyyat tam geri qaytarılır.
 */
export async function purchaseModel(params: {
  userId: string;
  modelId: string;
}): Promise<{
  entitlementId: string;
  creditsSpent: number;
  alreadyOwned: boolean;
  expiresAt: Date;
}> {
  const { userId, modelId } = params;

  return prisma.$transaction(async (tx) => {
    // Hələ qüvvədə olan hüquq varsa, yenisi alınmır.
    const active = await tx.entitlement.findFirst({
      where: { userId, modelId, expiresAt: { gt: new Date() } },
      orderBy: { expiresAt: "desc" },
      select: { id: true, creditsSpent: true, expiresAt: true },
    });
    if (active) {
      return {
        entitlementId: active.id,
        creditsSpent: active.creditsSpent,
        alreadyOwned: true,
        expiresAt: active.expiresAt,
      };
    }

    const model = await tx.model.findUnique({
      where: { id: modelId },
      select: {
        id: true,
        status: true,
        creditCost: true,
        authorId: true,
        isOfficial: true,
      },
    });
    if (!model) throw new CreditError("Model tapılmadı", "NOT_FOUND");
    if (model.status !== "PUBLISHED") {
      throw new CreditError("Bu model əlçatan deyil", "NOT_AVAILABLE");
    }

    // Müəllif öz modelini pulsuz endirir.
    const cost = model.authorId === userId ? 0 : model.creditCost;

    if (cost > 0) {
      await consumeFromLots(tx, userId, cost);
      const balance = await getValidBalance(userId, tx);

      await tx.creditTransaction.create({
        data: {
          userId,
          amount: -cost,
          reason: "DOWNLOAD_SPEND",
          balanceAfter: balance,
          modelId,
        },
      });

      await tx.user.update({
        where: { id: userId },
        data: { creditBalance: balance },
      });
    }

    const expiresAt = new Date(Date.now() + DOWNLOAD_WINDOW_HOURS * 60 * 60 * 1000);

    const entitlement = await tx.entitlement.create({
      data: { userId, modelId, creditsSpent: cost, expiresAt },
      select: { id: true },
    });

    // Artist payı (60/40). Platformanın öz modellərində və müəllifin öz
    // modelini endirməsində qazanc yazısı yaradılmır.
    if (cost > 0 && !model.isOfficial && model.authorId !== userId) {
      await tx.artistEarning.create({
        data: {
          artistId: model.authorId,
          modelId,
          entitlementId: entitlement.id,
          creditsGross: cost,
          creditsNet: artistShareOf(cost),
        },
      });
    }

    await tx.model.update({
      where: { id: modelId },
      data: { downloadCount: { increment: 1 } },
    });

    return {
      entitlementId: entitlement.id,
      creditsSpent: cost,
      alreadyOwned: false,
      expiresAt,
    };
  });
}

/**
 * İstifadəçinin modeli ENDİRƏ biləcəyi qüvvədə hüququ varmı?
 * Müddəti keçmiş hüquq nəzərə alınmır.
 */
export async function getActiveEntitlement(
  userId: string,
  modelId: string,
): Promise<{ id: string; expiresAt: Date } | null> {
  return prisma.entitlement.findFirst({
    where: { userId, modelId, expiresAt: { gt: new Date() } },
    orderBy: { expiresAt: "desc" },
    select: { id: true, expiresAt: true },
  });
}

export async function hasEntitlement(userId: string, modelId: string): Promise<boolean> {
  return (await getActiveEntitlement(userId, modelId)) !== null;
}
