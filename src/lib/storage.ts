import "server-only";

import { createReadStream } from "node:fs";
import { mkdir, stat, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

/**
 * Fayl saxlama abstraksiyası.
 *
 * MVP-də lokal diskdə saxlanılır. S3/R2-yə keçmək üçün yalnız bu faylı
 * dəyişmək kifayətdir — qalan kod `storageKey` ilə işləyir, fiziki yolla yox.
 *
 * VACİB: STORAGE_ROOT `public/` qovluğundan KƏNARDADIR. Yəni satılan fayllar
 * heç bir halda birbaşa URL ilə oxuna bilmir; yeganə giriş yolu /api/download-dır.
 */

// turbopackIgnore: bu yollar runtime-da həll olunur; olmasa Turbopack bütün
// layihəni trace edib serverin çıxışına daxil edir.
const STORAGE_ROOT = path.resolve(/* turbopackIgnore: true */ process.env.STORAGE_ROOT ?? "./storage");

function resolveKey(key: string): string {
  const full = path.resolve(STORAGE_ROOT, key);
  // Path traversal müdafiəsi: "../" ilə kökdən kənara çıxmağa icazə yoxdur.
  if (full !== STORAGE_ROOT && !full.startsWith(STORAGE_ROOT + path.sep)) {
    throw new Error("Yolverilməz storage açarı");
  }
  return full;
}

/** Təhlükəsiz fayl adı yaradır (istifadəçinin verdiyi ad birbaşa işlədilmir). */
export function makeStorageKey(prefix: string, originalName: string): string {
  const ext = path.extname(originalName).toLowerCase().slice(0, 12);
  const safeExt = /^\.[a-z0-9.]+$/.test(ext) ? ext : "";
  return `${prefix}/${randomUUID()}${safeExt}`;
}

export async function putObject(key: string, data: Buffer): Promise<void> {
  const full = resolveKey(key);
  await mkdir(path.dirname(full), { recursive: true });
  await writeFile(full, data);
}

export async function objectSize(key: string): Promise<number> {
  const info = await stat(resolveKey(key));
  return info.size;
}

export async function objectExists(key: string): Promise<boolean> {
  try {
    await stat(resolveKey(key));
    return true;
  } catch {
    return false;
  }
}

export function readObjectStream(key: string): NodeJS.ReadableStream {
  return createReadStream(resolveKey(key));
}

export async function deleteObject(key: string): Promise<void> {
  try {
    await unlink(resolveKey(key));
  } catch {
    // Fayl onsuz da yoxdursa, susmaq düzgündür.
  }
}

/**
 * Açıq fayllar (preview .glb, render şəkilləri) `public/uploads` altında
 * saxlanılır və birbaşa URL ilə verilir — bunlar satılan məhsul deyil.
 */
const PUBLIC_ROOT = path.resolve(/* turbopackIgnore: true */ "./public/uploads");

export function publicUrl(key: string): string {
  return `/uploads/${key}`;
}

export async function putPublicObject(key: string, data: Buffer): Promise<string> {
  const full = path.resolve(PUBLIC_ROOT, key);
  if (!full.startsWith(PUBLIC_ROOT + path.sep)) {
    throw new Error("Yolverilməz public açar");
  }
  await mkdir(path.dirname(full), { recursive: true });
  await writeFile(full, data);
  return publicUrl(key);
}
