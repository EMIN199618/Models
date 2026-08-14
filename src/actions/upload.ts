"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";

import { requireRole } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { makeStorageKey, putObject, putPublicObject } from "@/lib/storage";

/**
 * Model yükləmə.
 *
 * QEYD (istehsal üçün): burada fayllar server üzərindən keçir. Arxviz
 * modelləri 100 MB–2 GB ola bildiyi üçün istehsalda birbaşa S3-ə presigned
 * URL ilə yükləmə tətbiq edilməlidir — server yalnız metadata qəbul edər.
 */

const MAX_SOURCE_BYTES = 500 * 1024 * 1024; // 500 MB
const MAX_PREVIEW_BYTES = 30 * 1024 * 1024; // 30 MB
const MAX_IMAGE_BYTES = 8 * 1024 * 1024; // 8 MB

const SOURCE_EXT = [".zip", ".rar", ".7z", ".max", ".fbx", ".obj", ".blend"];
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

export type UploadState = { error?: string } | undefined;

const metaSchema = z.object({
  title: z.string().trim().min(3, "Başlıq ən azı 3 simvol olmalıdır").max(140),
  description: z.string().trim().max(5000).default(""),
  categorySlug: z.string().trim().optional(),
  creditCost: z.coerce.number().int().min(0, "Qiymət mənfi ola bilməz").max(100),
  renderer: z.enum(["CORONA", "VRAY", "BOTH", "OTHER"]),
  formats: z.string().trim().default(""),
  maxVersion: z.string().trim().max(20).optional(),
  polyCount: z.coerce.number().int().min(0).optional(),
  hasTextures: z.boolean().default(false),
  isPbr: z.boolean().default(false),
  tags: z.string().trim().default(""),
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
    .slice(0, 70);
}

function hasAllowedExt(name: string, allowed: string[]): boolean {
  const lower = name.toLowerCase();
  return allowed.some((ext) => lower.endsWith(ext));
}

export async function createModelAction(
  _prev: UploadState,
  formData: FormData,
): Promise<UploadState> {
  const user = await requireRole("ARTIST", "ADMIN");

  const parsed = metaSchema.safeParse({
    title: formData.get("title"),
    description: formData.get("description") ?? "",
    categorySlug: formData.get("categorySlug") || undefined,
    creditCost: formData.get("creditCost") ?? 1,
    renderer: formData.get("renderer") ?? "OTHER",
    formats: formData.get("formats") ?? "",
    maxVersion: formData.get("maxVersion") || undefined,
    polyCount: formData.get("polyCount") || undefined,
    hasTextures: formData.get("hasTextures") === "on",
    isPbr: formData.get("isPbr") === "on",
    tags: formData.get("tags") ?? "",
  });

  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message ?? "Məlumatlar düzgün deyil" };
  }
  const meta = parsed.data;

  // --- faylların yoxlanması ---
  const sourceFile = formData.get("sourceFile");
  if (!(sourceFile instanceof File) || sourceFile.size === 0) {
    return { error: "Mənbə faylı (model arxivi) tələb olunur" };
  }
  if (!hasAllowedExt(sourceFile.name, SOURCE_EXT)) {
    return { error: `Mənbə faylının formatı dəstəklənmir (${SOURCE_EXT.join(", ")})` };
  }
  if (sourceFile.size > MAX_SOURCE_BYTES) {
    return { error: "Mənbə faylı 500 MB-dan böyükdür" };
  }

  const previewFile = formData.get("previewGlb");
  const hasPreview = previewFile instanceof File && previewFile.size > 0;
  if (hasPreview) {
    if (!previewFile.name.toLowerCase().endsWith(".glb")) {
      return { error: "Önizləmə faylı .glb formatında olmalıdır" };
    }
    if (previewFile.size > MAX_PREVIEW_BYTES) {
      return { error: "Önizləmə faylı 30 MB-dan böyükdür" };
    }
  }

  const imageFiles = formData
    .getAll("images")
    .filter((f): f is File => f instanceof File && f.size > 0);
  if (imageFiles.length === 0) {
    return { error: "Ən azı bir render şəkli əlavə edin" };
  }
  for (const img of imageFiles) {
    if (!IMAGE_TYPES.includes(img.type)) {
      return { error: "Şəkillər yalnız JPG, PNG və ya WebP ola bilər" };
    }
    if (img.size > MAX_IMAGE_BYTES) {
      return { error: "Hər şəkil 8 MB-dan kiçik olmalıdır" };
    }
  }

  // --- unikal slug ---
  const base = slugify(meta.title) || "model";
  let slug = base;
  for (let i = 2; await prisma.model.findUnique({ where: { slug } }); i++) {
    slug = `${base}-${i}`;
  }

  const formats = meta.formats
    .split(",")
    .map((f) => f.trim().toLowerCase().replace(/^\./, ""))
    .filter(Boolean)
    .slice(0, 8);

  const tagNames = meta.tags
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 12);

  const category = meta.categorySlug
    ? await prisma.category.findUnique({
        where: { slug: meta.categorySlug },
        select: { id: true },
      })
    : null;

  // --- fayllar diskə ---
  // Mənbə faylı QORUNAN storage-a (public-dən kənar), önizləmələr isə public-ə.
  const sourceKey = makeStorageKey("source", sourceFile.name);
  await putObject(sourceKey, Buffer.from(await sourceFile.arrayBuffer()));

  const model = await prisma.model.create({
    data: {
      slug,
      title: meta.title,
      description: meta.description,
      status: "PENDING", // hər yeni model moderasiyaya düşür
      authorId: user.id,
      isOfficial: user.role === "ADMIN",
      categoryId: category?.id ?? null,
      creditCost: meta.creditCost,
      renderer: meta.renderer,
      formats,
      maxVersion: meta.maxVersion ?? null,
      polyCount: meta.polyCount ?? null,
      hasTextures: meta.hasTextures,
      isPbr: meta.isPbr,
      fileSizeBytes: BigInt(sourceFile.size),
      assets: {
        create: {
          kind: "SOURCE",
          storageKey: sourceKey,
          originalName: sourceFile.name,
          mimeType: sourceFile.type || "application/octet-stream",
          sizeBytes: BigInt(sourceFile.size),
        },
      },
    },
    select: { id: true, slug: true },
  });

  if (hasPreview) {
    const key = makeStorageKey(`models/${model.id}`, previewFile.name);
    await putPublicObject(key, Buffer.from(await previewFile.arrayBuffer()));
    await prisma.asset.create({
      data: {
        modelId: model.id,
        kind: "PREVIEW_GLB",
        storageKey: key,
        originalName: previewFile.name,
        mimeType: "model/gltf-binary",
        sizeBytes: BigInt(previewFile.size),
      },
    });
  }

  for (const [index, img] of imageFiles.entries()) {
    const key = makeStorageKey(`models/${model.id}`, img.name);
    await putPublicObject(key, Buffer.from(await img.arrayBuffer()));
    await prisma.asset.create({
      data: {
        modelId: model.id,
        kind: "IMAGE",
        storageKey: key,
        originalName: img.name,
        mimeType: img.type,
        sizeBytes: BigInt(img.size),
        sortOrder: index,
      },
    });
  }

  for (const name of tagNames) {
    const tagSlug = slugify(name);
    if (!tagSlug) continue;
    const tag = await prisma.tag.upsert({
      where: { slug: tagSlug },
      create: { slug: tagSlug, name },
      update: {},
      select: { id: true },
    });
    await prisma.modelTag.upsert({
      where: { modelId_tagId: { modelId: model.id, tagId: tag.id } },
      create: { modelId: model.id, tagId: tag.id },
      update: {},
    });
  }

  revalidatePath("/studio");
  redirect("/studio?uploaded=1");
}
