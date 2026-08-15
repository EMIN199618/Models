import "dotenv/config";

import Module from "node:module";
import { createHash, randomBytes } from "node:crypto";

// `server-only` paketi Next-dən kənarda import olunanda xəta atır.
// Test skripti Node-da işlədiyi üçün onu boş modula əvəz edirik.
const moduleLoad = (Module as unknown as { _load: (...a: unknown[]) => unknown })._load;
(Module as unknown as { _load: (...a: unknown[]) => unknown })._load = function (
  this: unknown,
  request: unknown,
  ...rest: unknown[]
) {
  if (request === "server-only") return {};
  return moduleLoad.call(this, request, ...rest);
};

import { PrismaPg } from "@prisma/adapter-pg";

import { PrismaClient } from "../src/generated/prisma/client.js";

/**
 * Uçdan-uca yoxlama: alış və qorunan endirmə axını.
 *
 * Yoxlanan hallar:
 *  1. Sessiyasız endirmə  → 401
 *  2. Alınmamış model     → 403
 *  3. Credit ilə alış     → balans azalır, ledger yazılır
 *  4. Alındıqdan sonra    → 200 + faylın özü
 *  5. Təkrar alış         → Credit İKİNCİ DƏFƏ tutulmur
 *  6. Balans çatmayanda   → alış rədd edilir, balans dəyişmir
 *  7. İmzalı token vaxtı  → saxta token 403
 */

const BASE = process.env.BASE_URL ?? "http://localhost:3000";

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

/** Test üçün birbaşa DB-də sessiya yaradır və cookie dəyərini qaytarır. */
async function makeSession(userId: string): Promise<string> {
  const token = randomBytes(32).toString("hex");
  await prisma.session.create({
    data: {
      tokenHash: createHash("sha256").update(token).digest("hex"),
      userId,
      expiresAt: new Date(Date.now() + 3600_000),
    },
  });
  return `m3d_session=${token}`;
}


/** Test üçün balansı sıfırlayıb bir lot yaradır (Credit-lər lot əsaslıdır). */
async function setBalance(userId: string, amount: number): Promise<void> {
  await prisma.creditTransaction.deleteMany({ where: { userId } });
  if (amount > 0) {
    await prisma.creditTransaction.create({
      data: {
        userId,
        amount,
        reason: "ADMIN_GRANT",
        balanceAfter: amount,
        remaining: amount,
        expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
      },
    });
  }
  await prisma.user.update({ where: { id: userId }, data: { creditBalance: amount } });
}

async function main() {
  const { purchaseModel, CreditError, getValidBalance } = await import(
    "../src/lib/credits.js"
  );

  const buyer = await prisma.user.findUniqueOrThrow({
    where: { email: "dizayner@example.com" },
  });
  const paidModel = await prisma.model.findFirstOrThrow({
    where: { status: "PUBLISHED", creditCost: { gt: 0 } },
    orderBy: { creditCost: "asc" },
  });

  // Təmiz başlanğıc
  await prisma.entitlement.deleteMany({ where: { userId: buyer.id } });
  await setBalance(buyer.id, 25);

  const cookie = await makeSession(buyer.id);

  console.log(`\nModel: "${paidModel.title}" (${paidModel.creditCost} Credit)\n`);

  // 1 — sessiyasız
  const anon = await fetch(`${BASE}/api/download/${paidModel.id}`, { redirect: "manual" });
  check("Sessiyasız endirmə rədd edilir", anon.status === 401, `(status ${anon.status})`);

  // 2 — girişli, amma alınmayıb
  const notOwned = await fetch(`${BASE}/api/download/${paidModel.id}`, {
    headers: { cookie },
    redirect: "manual",
  });
  check(
    "Alınmamış model üçün endirmə rədd edilir",
    notOwned.status === 403,
    `(status ${notOwned.status})`,
  );

  // 3 — alış
  const before = 25;
  await purchaseModel({ userId: buyer.id, modelId: paidModel.id });
  const afterUser = { creditBalance: await getValidBalance(buyer.id) };
  check(
    "Alışdan sonra balans düzgün azalır",
    afterUser.creditBalance === before - paidModel.creditCost,
    `(gözlənilən ${before - paidModel.creditCost}, alınan ${afterUser.creditBalance})`,
  );

  const ledger = await prisma.creditTransaction.findFirst({
    where: { userId: buyer.id, reason: "DOWNLOAD_SPEND" },
    orderBy: { createdAt: "desc" },
  });
  check(
    "Ledger yazısı yaradılır və balansla uyğundur",
    ledger?.amount === -paidModel.creditCost &&
      ledger?.balanceAfter === afterUser.creditBalance,
  );

  // 4 — alındıqdan sonra endirmə
  const owned = await fetch(`${BASE}/api/download/${paidModel.id}`, {
    headers: { cookie },
    redirect: "follow",
  });
  const body = Buffer.from(await owned.arrayBuffer());
  check("Alınmış model endirilir", owned.status === 200, `(status ${owned.status})`);
  check(
    "Endirilən fayl həqiqi ZIP-dir",
    body.length > 0 && body.subarray(0, 2).toString("ascii") === "PK",
    `(ilk baytlar: ${body.subarray(0, 2).toString("hex")})`,
  );
  check(
    "Content-Disposition attachment qaytarılır",
    (owned.headers.get("content-disposition") ?? "").startsWith("attachment"),
  );

  // 5 — endirmə pəncərəsi açıq ikən təkrar alış Credit tutmur
  const balanceBeforeRepeat = afterUser.creditBalance;
  const repeat = await purchaseModel({ userId: buyer.id, modelId: paidModel.id });
  const afterRepeat = { creditBalance: await getValidBalance(buyer.id) };
  check(
    "Endirmə pəncərəsi açıq ikən təkrar Credit tutulmur",
    repeat.alreadyOwned === true && afterRepeat.creditBalance === balanceBeforeRepeat,
  );

  // 5b — pəncərə bitəndən sonra yeni alış TƏLƏB OLUNUR (təkrar endirmə pulsuz deyil)
  await prisma.entitlement.updateMany({
    where: { userId: buyer.id, modelId: paidModel.id },
    data: { expiresAt: new Date(Date.now() - 1000) },
  });
  const expiredAccess = await fetch(`${BASE}/api/download/${paidModel.id}`, {
    headers: { cookie },
    redirect: "manual",
  });
  check(
    "Müddəti bitmiş hüquqla endirmə rədd edilir",
    expiredAccess.status === 403,
    `(status ${expiredAccess.status})`,
  );

  const balanceBeforeRebuy = await getValidBalance(buyer.id);
  const rebuy = await purchaseModel({ userId: buyer.id, modelId: paidModel.id });
  const afterRebuy = { creditBalance: await getValidBalance(buyer.id) };
  check(
    "Müddət bitəndən sonra təkrar alış Credit tutur",
    rebuy.alreadyOwned === false &&
      afterRebuy.creditBalance === balanceBeforeRebuy - paidModel.creditCost,
    `(${balanceBeforeRebuy} → ${afterRebuy.creditBalance})`,
  );

  // 6 — balans çatmır
  await setBalance(buyer.id, 0);
  const expensive = await prisma.model.findFirstOrThrow({
    where: { status: "PUBLISHED", creditCost: { gt: 0 }, id: { not: paidModel.id } },
  });
  let rejected = false;
  try {
    await purchaseModel({ userId: buyer.id, modelId: expensive.id });
  } catch (e) {
    rejected = e instanceof CreditError && e.code === "INSUFFICIENT";
  }
  const afterFail = { creditBalance: await getValidBalance(buyer.id) };
  const entitlementCount = await prisma.entitlement.count({
    where: { userId: buyer.id, modelId: expensive.id },
  });
  check("Balans çatmayanda alış rədd edilir", rejected);
  check("Uğursuz alışda balans dəyişmir", afterFail.creditBalance === 0);
  check("Uğursuz alışda endirmə hüququ yaranmır", entitlementCount === 0);

  // 7 — saxta imzalı token
  const fake = await fetch(`${BASE}/api/file?token=saxta.token.deyeri`, {
    redirect: "manual",
  });
  check("Saxta endirmə tokeni rədd edilir", fake.status === 403, `(status ${fake.status})`);

  // 8 — preview .glb açıqdır (satılan fayl deyil)
  const previewAsset = await prisma.asset.findFirst({
    where: { modelId: paidModel.id, kind: "PREVIEW_GLB" },
  });
  if (previewAsset) {
    const glb = await fetch(`${BASE}/uploads/${previewAsset.storageKey}`);
    const glbBody = Buffer.from(await glb.arrayBuffer());
    check(
      "Preview .glb hamıya açıqdır və düzgün formatdadır",
      glb.status === 200 && glbBody.subarray(0, 4).toString("ascii") === "glTF",
    );
  }

  console.log(`\nNəticə: ${passed} keçdi, ${failed} uğursuz\n`);
  if (failed > 0) process.exitCode = 1;
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
