import "server-only";

import { createHash, randomBytes } from "node:crypto";
import { cookies } from "next/headers";
import bcrypt from "bcryptjs";

import { prisma } from "@/lib/prisma";
import type { Role } from "@/generated/prisma/enums";

const SESSION_COOKIE = "m3d_session";
const SESSION_TTL_DAYS = 30;

export type SessionUser = {
  id: string;
  email: string;
  name: string;
  role: Role;
  slug: string | null;
  creditBalance: number;
};

// --- parol ---------------------------------------------------------------

export function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, 12);
}

export function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}

// --- sessiya -------------------------------------------------------------

/**
 * Cookie-də xam təsadüfi token saxlanılır, bazada isə yalnız onun SHA-256
 * hash-i. Baza sızsa belə, hazır sessiya tokenləri əldə edilə bilməz.
 */
function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export async function createSession(
  userId: string,
  meta: { ip?: string | null; userAgent?: string | null } = {},
): Promise<void> {
  const token = randomBytes(32).toString("hex");
  const expiresAt = new Date(Date.now() + SESSION_TTL_DAYS * 24 * 60 * 60 * 1000);

  await prisma.session.create({
    data: {
      tokenHash: hashToken(token),
      userId,
      ip: meta.ip ?? null,
      userAgent: meta.userAgent ?? null,
      expiresAt,
    },
  });

  const store = await cookies();
  store.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: expiresAt,
  });
}

export async function destroySession(): Promise<void> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  if (token) {
    await prisma.session.deleteMany({ where: { tokenHash: hashToken(token) } });
  }
  store.delete(SESSION_COOKIE);
}

/** Cari istifadəçi, yoxdursa null. Server komponentlərində və API-larda işlənir. */
export async function getCurrentUser(): Promise<SessionUser | null> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  if (!token) return null;

  const session = await prisma.session.findUnique({
    where: { tokenHash: hashToken(token) },
    select: {
      expiresAt: true,
      user: {
        select: {
          id: true,
          email: true,
          name: true,
          role: true,
          slug: true,
          creditBalance: true,
        },
      },
    },
  });

  if (!session || session.expiresAt < new Date()) return null;

  // Balans lotlardan hesablanır ki, müddəti bitmiş Credit-lər görünməsin.
  // (Saxlanılan `creditBalance` sütunu son yazma anındakı vəziyyəti göstərir.)
  const { getValidBalance } = await import("@/lib/credits");
  const creditBalance = await getValidBalance(session.user.id);

  return { ...session.user, creditBalance };
}

// --- icazə yoxlamaları ---------------------------------------------------

export class AuthError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function requireUser(): Promise<SessionUser> {
  const user = await getCurrentUser();
  if (!user) throw new AuthError("Giriş tələb olunur", 401);
  return user;
}

export async function requireRole(...roles: Role[]): Promise<SessionUser> {
  const user = await requireUser();
  if (!roles.includes(user.role)) {
    throw new AuthError("Bu əməliyyat üçün icazəniz yoxdur", 403);
  }
  return user;
}
