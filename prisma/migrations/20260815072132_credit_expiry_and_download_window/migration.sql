/*
  Warnings:

  - Added the required column `expiresAt` to the `Entitlement` table without a default value. This is not possible if the table is not empty.

*/
-- DropIndex
DROP INDEX "Entitlement_userId_modelId_key";

-- AlterTable
ALTER TABLE "CreditTransaction" ADD COLUMN     "expiresAt" TIMESTAMP(3),
ADD COLUMN     "remaining" INTEGER NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "Entitlement" ADD COLUMN     "expiresAt" TIMESTAMP(3) NOT NULL;

-- CreateIndex
CREATE INDEX "CreditTransaction_userId_expiresAt_idx" ON "CreditTransaction"("userId", "expiresAt");

-- CreateIndex
CREATE INDEX "Entitlement_userId_modelId_expiresAt_idx" ON "Entitlement"("userId", "modelId", "expiresAt");
