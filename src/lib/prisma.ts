import { PrismaClient } from "@/generated/prisma/client";

// Next.js dev rejimində hot-reload hər dəfə yeni client yaratmasın deyə
// global obyektdə saxlanılır.
const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
