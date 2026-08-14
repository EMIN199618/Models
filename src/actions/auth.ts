"use server";

import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { z } from "zod";

import { prisma } from "@/lib/prisma";
import { createSession, destroySession, hashPassword, verifyPassword } from "@/lib/auth";
import { grantCredits } from "@/lib/credits";
import { REFERRAL_BONUS_CREDITS, REFERRAL_BONUS_TRIGGER } from "@/lib/pricing";

/**
 * Yeni istifadəçiyə verilən başlanğıc Credit hədiyyəsi.
 * 0 = hədiyyə yoxdur; Credit yalnız paket alınmaqla və ya dəvət kodu ilə gəlir.
 */
const SIGNUP_BONUS_CREDITS = 0;

export type ActionState = { error?: string } | undefined;

const registerSchema = z.object({
  name: z.string().trim().min(2, "Ad ən azı 2 simvol olmalıdır").max(80),
  email: z.string().trim().toLowerCase().email("E-poçt düzgün deyil"),
  password: z.string().min(8, "Parol ən azı 8 simvol olmalıdır").max(200),
  isArtist: z.boolean().default(false),
  referralCode: z.string().trim().max(60).optional(),
});

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[əƏ]/g, "e")
    .replace(/[ıİ]/g, "i")
    .replace(/[öÖ]/g, "o")
    .replace(/[üÜ]/g, "u")
    .replace(/[çÇ]/g, "c")
    .replace(/[şŞ]/g, "s")
    .replace(/[ğĞ]/g, "g")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

async function requestMeta() {
  const h = await headers();
  return {
    ip: h.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null,
    userAgent: h.get("user-agent"),
  };
}

export async function registerAction(
  _prev: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const parsed = registerSchema.safeParse({
    name: formData.get("name"),
    email: formData.get("email"),
    password: formData.get("password"),
    isArtist: formData.get("isArtist") === "on",
    referralCode: String(formData.get("referralCode") ?? "").trim() || undefined,
  });

  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message ?? "Məlumatlar düzgün deyil" };
  }
  const { name, email, password, isArtist, referralCode } = parsed.data;

  const existing = await prisma.user.findUnique({
    where: { email },
    select: { id: true },
  });
  if (existing) return { error: "Bu e-poçt artıq qeydiyyatdan keçib" };

  // Artist üçün unikal profil slug-ı
  let slug: string | null = null;
  if (isArtist) {
    const base = slugify(name) || "artist";
    slug = base;
    for (let i = 2; await prisma.user.findUnique({ where: { slug } }); i++) {
      slug = `${base}-${i}`;
    }
  }

  // Dəvət kodu — yazılıbsa, yoxlanır. Yanlış kod qeydiyyatı bloklamır,
  // sadəcə bonus verilmir (istifadəçi səhv yazıbsa da hesab yaransın).
  let referrer: { id: string } | null = null;
  if (referralCode) {
    referrer = await prisma.user.findUnique({
      where: { referralCode },
      select: { id: true },
    });
    if (!referrer) return { error: "Dəvət kodu tapılmadı — yoxlayıb yenidən yazın" };
  }

  const user = await prisma.user.create({
    data: {
      name,
      email,
      passwordHash: await hashPassword(password),
      role: isArtist ? "ARTIST" : "USER",
      slug,
      referredById: referrer?.id ?? null,
    },
    select: { id: true },
  });

  if (SIGNUP_BONUS_CREDITS > 0) {
    await grantCredits({
      userId: user.id,
      amount: SIGNUP_BONUS_CREDITS,
      reason: "SIGNUP_BONUS",
      note: "Qeydiyyat hədiyyəsi",
    });
  }

  // Dəvət bonusu. Trigger "FIRST_PURCHASE"-dirsə, burada verilmir —
  // ilk paket ödənişi təsdiqlənəndə verilir (bax src/lib/pricing.ts).
  if (referrer && REFERRAL_BONUS_TRIGGER === "REGISTRATION") {
    await grantCredits({
      userId: user.id,
      amount: REFERRAL_BONUS_CREDITS,
      reason: "REFERRAL",
      note: "Dəvət kodu bonusu",
    });
  }

  await createSession(user.id, await requestMeta());
  redirect(isArtist ? "/studio" : "/models");
}

const loginSchema = z.object({
  email: z.string().trim().toLowerCase().email("E-poçt düzgün deyil"),
  password: z.string().min(1, "Parol tələb olunur"),
});

export async function loginAction(
  _prev: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const parsed = loginSchema.safeParse({
    email: formData.get("email"),
    password: formData.get("password"),
  });
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message ?? "Məlumatlar düzgün deyil" };
  }

  const user = await prisma.user.findUnique({
    where: { email: parsed.data.email },
    select: { id: true, passwordHash: true, role: true },
  });

  // Eyni mesaj: hansı e-poçtun mövcud olduğunu üzə çıxarmırıq.
  const ok = user ? await verifyPassword(parsed.data.password, user.passwordHash) : false;
  if (!user || !ok) return { error: "E-poçt və ya parol yanlışdır" };

  await createSession(user.id, await requestMeta());
  redirect(user.role === "USER" ? "/models" : "/studio");
}

export async function logoutAction(): Promise<void> {
  await destroySession();
  redirect("/");
}
