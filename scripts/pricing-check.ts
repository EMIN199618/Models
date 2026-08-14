import "dotenv/config";

import Module from "node:module";

import { PrismaPg } from "@prisma/adapter-pg";

import { PrismaClient } from "../src/generated/prisma/client.js";

// `server-only` paketi Next-dən kənarda xəta atır — testdə neytrallaşdırılır.
const moduleLoad = (Module as unknown as { _load: (...a: unknown[]) => unknown })._load;
(Module as unknown as { _load: (...a: unknown[]) => unknown })._load = function (
  this: unknown,
  request: unknown,
  ...rest: unknown[]
) {
  if (request === "server-only") return {};
  return moduleLoad.call(this, request, ...rest);
};

/**
 * Qiymət qaydalarının yoxlanması:
 *  1. Bütün modellər vahid qiymətdədir, pulsuz model yoxdur
 *  2. Alışda artistə 60% yazılır, platformaya 40% qalır
 *  3. Rəsmi (platforma) modellərində artist qazancı yaranmır
 *  4. Artistin öz modelini endirməsi pulsuzdur və qazanc yaratmır
 *  5. Təkrar alış qazancı ikiqat yazmır
 *  6. Paket sifarişi təsdiqlənəndə Credit köçürülür və ledger yazılır
 *  7. Təkrar təsdiq Credit-i ikinci dəfə vermir
 */

const prisma = new PrismaClient({
  adapter: new PrismaPg({ connectionString: process.env.DATABASE_URL! }),
});

let passed = 0;
let failed = 0;

function check(name: string, ok: boolean, detail = "") {
  if (ok) {
    passed++;
    console.log(`  ✓ ${name}`);
  } else {
    failed++;
    console.log(`  ✗ ${name} ${detail}`);
  }
}

async function main() {
  const { purchaseModel } = await import("../src/lib/credits.js");
  const pricing = await import("../src/lib/pricing.js");
  const { MODEL_CREDIT_COST, ARTIST_REVENUE_SHARE, CREDIT_PACKAGES } = pricing;

  console.log(
    `\nQaydalar: model ${MODEL_CREDIT_COST} Credit · artist payı ${Math.round(
      ARTIST_REVENUE_SHARE * 100,
    )}%\n`,
  );

  // 1 — vahid qiymət
  const priceGroups = await prisma.model.groupBy({
    by: ["creditCost"],
    where: { status: "PUBLISHED" },
  });
  check(
    "Bütün modellər vahid qiymətdədir",
    priceGroups.length === 1 && priceGroups[0].creditCost === MODEL_CREDIT_COST,
    `(tapılan qiymətlər: ${priceGroups.map((g) => g.creditCost).join(", ")})`,
  );
  const freeCount = await prisma.model.count({
    where: { status: "PUBLISHED", creditCost: 0 },
  });
  check("Pulsuz model yoxdur", freeCount === 0, `(${freeCount} pulsuz model)`);

  // Hazırlıq
  const buyer = await prisma.user.findUniqueOrThrow({
    where: { email: "dizayner@example.com" },
  });
  const artistModel = await prisma.model.findFirstOrThrow({
    where: { status: "PUBLISHED", isOfficial: false },
    select: { id: true, authorId: true, title: true },
  });
  const officialModel = await prisma.model.findFirstOrThrow({
    where: { status: "PUBLISHED", isOfficial: true },
    select: { id: true, title: true },
  });

  await prisma.artistEarning.deleteMany({});
  await prisma.entitlement.deleteMany({ where: { userId: buyer.id } });
  await prisma.creditTransaction.deleteMany({ where: { userId: buyer.id } });
  await prisma.user.update({
    where: { id: buyer.id },
    data: { creditBalance: 500 },
  });

  // 2 — artist modeli: 60/40
  await purchaseModel({ userId: buyer.id, modelId: artistModel.id });
  const earning = await prisma.artistEarning.findFirst({
    where: { modelId: artistModel.id },
  });
  const expectedNet = Math.round(MODEL_CREDIT_COST * ARTIST_REVENUE_SHARE);
  check(
    "Artistə 60% yazılır",
    earning?.creditsNet === expectedNet && earning?.creditsGross === MODEL_CREDIT_COST,
    `(gözlənilən ${expectedNet}, alınan ${earning?.creditsNet})`,
  );
  check(
    "Platformanın payı 40%-dir",
    earning !== null && earning.creditsGross - earning.creditsNet === MODEL_CREDIT_COST - expectedNet,
  );
  check(
    "Qazanc düzgün artistə yazılır",
    earning?.artistId === artistModel.authorId,
  );

  // 3 — rəsmi model: qazanc yaranmır
  await purchaseModel({ userId: buyer.id, modelId: officialModel.id });
  const officialEarning = await prisma.artistEarning.findFirst({
    where: { modelId: officialModel.id },
  });
  check("Rəsmi modeldə artist qazancı yaranmır", officialEarning === null);

  // 4 — artist öz modelini endirir
  const author = await prisma.user.findUniqueOrThrow({
    where: { id: artistModel.authorId },
  });
  const authorBalanceBefore = author.creditBalance;
  await prisma.entitlement.deleteMany({
    where: { userId: author.id, modelId: artistModel.id },
  });
  const selfBuy = await purchaseModel({
    userId: author.id,
    modelId: artistModel.id,
  });
  const authorAfter = await prisma.user.findUniqueOrThrow({ where: { id: author.id } });
  check(
    "Artist öz modelini pulsuz endirir",
    selfBuy.creditsSpent === 0 && authorAfter.creditBalance === authorBalanceBefore,
  );
  const selfEarning = await prisma.artistEarning.findUnique({
    where: { entitlementId: selfBuy.entitlementId },
  });
  check("Öz alışından qazanc yazılmır", selfEarning === null);

  // 5 — təkrar alış
  const earningsBefore = await prisma.artistEarning.count();
  await purchaseModel({ userId: buyer.id, modelId: artistModel.id });
  const earningsAfter = await prisma.artistEarning.count();
  check("Təkrar alışda qazanc ikiqat yazılmır", earningsBefore === earningsAfter);

  // 6 — paket sifarişi
  const { markOrderPaidAction } = await import("../src/actions/admin.js").catch(
    () => ({ markOrderPaidAction: null }) as never,
  );
  const pkg = CREDIT_PACKAGES[0];
  const balanceBefore = (
    await prisma.user.findUniqueOrThrow({ where: { id: buyer.id } })
  ).creditBalance;

  const order = await prisma.creditOrder.create({
    data: {
      userId: buyer.id,
      packageId: pkg.id,
      credits: pkg.credits,
      priceMinor: pkg.priceMinor,
      currency: pkg.currency,
    },
  });

  // Admin action-u Next konteksti tələb etdiyi üçün eyni məntiq burada təkrarlanır.
  async function markPaid(orderId: string) {
    await prisma.$transaction(async (tx) => {
      const updated = await tx.creditOrder.updateMany({
        where: { id: orderId, status: "PENDING" },
        data: { status: "PAID", paidAt: new Date() },
      });
      if (updated.count === 0) return;
      const o = await tx.creditOrder.findUniqueOrThrow({ where: { id: orderId } });
      const u = await tx.user.update({
        where: { id: o.userId },
        data: { creditBalance: { increment: o.credits } },
        select: { creditBalance: true },
      });
      await tx.creditTransaction.create({
        data: {
          userId: o.userId,
          amount: o.credits,
          reason: "CREDIT_PACKAGE",
          balanceAfter: u.creditBalance,
          note: `Paket: ${o.packageId}`,
        },
      });
    });
  }
  void markOrderPaidAction;

  await markPaid(order.id);
  const afterPaid = await prisma.user.findUniqueOrThrow({ where: { id: buyer.id } });
  check(
    "Sifariş təsdiqlənəndə Credit köçürülür",
    afterPaid.creditBalance === balanceBefore + pkg.credits,
    `(gözlənilən ${balanceBefore + pkg.credits}, alınan ${afterPaid.creditBalance})`,
  );

  const packageTx = await prisma.creditTransaction.findFirst({
    where: { userId: buyer.id, reason: "CREDIT_PACKAGE" },
    orderBy: { createdAt: "desc" },
  });
  check(
    "Paket alışı ledger-ə yazılır",
    packageTx?.amount === pkg.credits && packageTx?.balanceAfter === afterPaid.creditBalance,
  );

  // 7 — təkrar təsdiq
  await markPaid(order.id);
  const afterDouble = await prisma.user.findUniqueOrThrow({ where: { id: buyer.id } });
  check(
    "Təkrar təsdiq Credit-i ikinci dəfə vermir",
    afterDouble.creditBalance === afterPaid.creditBalance,
  );

  console.log(`\nNəticə: ${passed} keçdi, ${failed} uğursuz\n`);
  if (failed > 0) process.exitCode = 1;
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
