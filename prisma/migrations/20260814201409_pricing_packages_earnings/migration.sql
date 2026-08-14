-- CreateEnum
CREATE TYPE "CreditOrderStatus" AS ENUM ('PENDING', 'PAID', 'CANCELED');

-- AlterEnum
ALTER TYPE "CreditReason" ADD VALUE 'CREDIT_PACKAGE';

-- AlterTable
ALTER TABLE "Model" ALTER COLUMN "creditCost" SET DEFAULT 10;

-- CreateTable
CREATE TABLE "CreditOrder" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "packageId" TEXT NOT NULL,
    "credits" INTEGER NOT NULL,
    "priceMinor" INTEGER NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'AZN',
    "status" "CreditOrderStatus" NOT NULL DEFAULT 'PENDING',
    "paidAt" TIMESTAMP(3),
    "note" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CreditOrder_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ArtistEarning" (
    "id" TEXT NOT NULL,
    "artistId" TEXT NOT NULL,
    "modelId" TEXT NOT NULL,
    "entitlementId" TEXT NOT NULL,
    "creditsGross" INTEGER NOT NULL,
    "creditsNet" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ArtistEarning_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "CreditOrder_status_createdAt_idx" ON "CreditOrder"("status", "createdAt");

-- CreateIndex
CREATE INDEX "CreditOrder_userId_createdAt_idx" ON "CreditOrder"("userId", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "ArtistEarning_entitlementId_key" ON "ArtistEarning"("entitlementId");

-- CreateIndex
CREATE INDEX "ArtistEarning_artistId_createdAt_idx" ON "ArtistEarning"("artistId", "createdAt");

-- CreateIndex
CREATE INDEX "ArtistEarning_modelId_idx" ON "ArtistEarning"("modelId");

-- AddForeignKey
ALTER TABLE "CreditOrder" ADD CONSTRAINT "CreditOrder_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ArtistEarning" ADD CONSTRAINT "ArtistEarning_artistId_fkey" FOREIGN KEY ("artistId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ArtistEarning" ADD CONSTRAINT "ArtistEarning_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "Model"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ArtistEarning" ADD CONSTRAINT "ArtistEarning_entitlementId_fkey" FOREIGN KEY ("entitlementId") REFERENCES "Entitlement"("id") ON DELETE CASCADE ON UPDATE CASCADE;
