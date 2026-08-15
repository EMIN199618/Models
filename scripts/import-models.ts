import "dotenv/config";

import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

import { PrismaPg } from "@prisma/adapter-pg";
import sharp from "sharp";

import { PrismaClient } from "../src/generated/prisma/client.js";
import { MODEL_CREDIT_COST } from "../src/lib/pricing.js";

/**
 * TOPLU IMPORT ALƏTİ
 *
 * Diskdəki qovluqdan modelləri oxuyub kataloqa yazır. Yüzlərlə modeli
 * bir əmrlə yükləmək üçündür.
 *
 * VACİB: yalnız hüququ sizdə olan modelləri yükləyin — sifarişlə
 * hazırlatdığınız, istehsalçıdan aldığınız və ya açıq lisenziyalı fayllar.
 *
 * Gözlənilən qovluq quruluşu:
 *
 *   import/
 *     divan/                        ← kateqoriya slug-ı (istəyə bağlı)
 *       modern-boz-divan/           ← model qovluğu
 *         model.zip                 ← mənbə fayl (məcburi)
 *         preview.glb               ← 3D önizləmə (istəyə bağlı)
 *         01.jpg  02.jpg            ← render şəkilləri (ən azı 1)
 *         meta.json                 ← metadata (istəyə bağlı)
 *
 * meta.json nümunəsi:
 *   {
 *     "title": "Modern boz divan",
 *     "description": "…",
 *     "category": "divan",
 *     "renderer": "CORONA",
 *     "formats": ["max", "fbx"],
 *     "maxVersion": "2021",
 *     "polyCount": 120000,
 *     "vertexCount": 65000,
 *     "hasTextures": true,
 *     "isPbr": true,
 *     "tags": ["divan", "modern"],
 *     "official": true
 *   }
 *
 * İstifadə:
 *   npm run import -- --dir ./import --author admin@arxvia.az
 *   npm run import -- --dir ./import --author admin@arxvia.az --publish
 *   npm run import -- --dir ./import --author admin@arxvia.az --dry-run
 */

// ---------------------------------------------------------------------------

const SOURCE_EXT = [".zip", ".rar", ".7z", ".max", ".fbx", ".obj", ".blend"];
const IMAGE_EXT = [".jpg", ".jpeg", ".png", ".webp"];
const MAX_IMAGE_WIDTH = 1600;

type Meta = {
  title?: string;
  description?: string;
  category?: string;
  renderer?: "CORONA" | "VRAY" | "BOTH" | "OTHER";
  formats?: string[];
  maxVersion?: string;
  polyCount?: number;
  vertexCount?: number;
  hasTextures?: boolean;
  isPbr?: boolean;
  tags?: string[];
  official?: boolean;
};

type Args = {
  dir: string;
  author: string;
  publish: boolean;
  dryRun: boolean;
};

function parseArgs(): Args {
  const argv = process.argv.slice(2);
  const get = (name: string): string | undefined => {
    const i = argv.indexOf(`--${name}`);
    return i >= 0 ? argv[i + 1] : undefined;
  };

  const dir = get("dir");
  const author = get("author");

  if (!dir || !author) {
    console.error(
      [
        "İstifadə:",
        "  npm run import -- --dir <qovluq> --author <e-poçt> [--publish] [--dry-run]",
        "",
        "  --dir       modellərin olduğu kök qovluq",
        "  --author    modellərin yazılacağı hesabın e-poçtu (ARTIST və ya ADMIN)",
        "  --publish   dərhal dərc et (standart: moderasiyaya göndərir)",
        "  --dry-run   heç nə yazma, yalnız nə olacağını göstər",
      ].join("\n"),
    );
    process.exit(1);
  }

  return {
    dir: path.resolve(dir),
    author,
    publish: argv.includes("--publish"),
    dryRun: argv.includes("--dry-run"),
  };
}

// ---------------------------------------------------------------------------

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

/** "modern-boz-divan" → "Modern boz divan" */
function titleFromFolder(name: string): string {
  const spaced = name.replace(/[-_]+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function hasExt(name: string, allowed: string[]): boolean {
  return allowed.includes(path.extname(name).toLowerCase());
}

type Found = {
  folder: string;
  categorySlug: string | null;
  source: string;
  preview: string | null;
  images: string[];
  meta: Meta;
};

/** Qovluğu gəzib model qovluqlarını tapır (bir və ya iki səviyyə dərinlikdə). */
async function discover(root: string): Promise<Found[]> {
  const found: Found[] = [];

  async function scan(dir: string, categorySlug: string | null, depth: number) {
    const entries = await readdir(dir, { withFileTypes: true });
    const files = entries.filter((e) => e.isFile()).map((e) => e.name);
    const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name);

    const source = files.find((f) => hasExt(f, SOURCE_EXT));

    if (source) {
      // Bu qovluq bir modeldir
      const images = files.filter((f) => hasExt(f, IMAGE_EXT)).sort();
      const preview = files.find((f) => f.toLowerCase().endsWith(".glb")) ?? null;

      let meta: Meta = {};
      if (files.includes("meta.json")) {
        try {
          meta = JSON.parse(await readFile(path.join(dir, "meta.json"), "utf8"));
        } catch (e) {
          console.warn(`  ! ${dir}: meta.json oxunmadı (${(e as Error).message})`);
        }
      }

      found.push({
        folder: dir,
        categorySlug: meta.category ?? categorySlug,
        source: path.join(dir, source),
        preview: preview ? path.join(dir, preview) : null,
        images: images.map((f) => path.join(dir, f)),
        meta,
      });
      return; // model qovluğunun içinə daha girmirik
    }

    // Model deyilsə, alt qovluqlara bax (ən çox 3 səviyyə)
    if (depth >= 3) return;
    for (const sub of dirs) {
      await scan(path.join(dir, sub), depth === 0 ? slugify(sub) : categorySlug, depth + 1);
    }
  }

  await scan(root, null, 0);
  return found;
}

// ---------------------------------------------------------------------------

const prisma = new PrismaClient({
  adapter: new PrismaPg({ connectionString: process.env.DATABASE_URL! }),
});

const STORAGE_ROOT = path.resolve(process.env.STORAGE_ROOT ?? "./storage");
const PUBLIC_UPLOADS = path.resolve("./public/uploads");

async function writeFileTo(root: string, key: string, data: Buffer): Promise<void> {
  const { mkdir, writeFile } = await import("node:fs/promises");
  const full = path.resolve(root, key);
  if (!full.startsWith(root + path.sep)) throw new Error("Yolverilməz açar");
  await mkdir(path.dirname(full), { recursive: true });
  await writeFile(full, data);
}

async function main() {
  const args = parseArgs();

  console.log(`\nQovluq:  ${args.dir}`);
  console.log(`Müəllif: ${args.author}`);
  console.log(`Rejim:   ${args.dryRun ? "DRY-RUN (yazılmır)" : args.publish ? "dərc et" : "moderasiyaya göndər"}\n`);

  try {
    await stat(args.dir);
  } catch {
    console.error(`Qovluq tapılmadı: ${args.dir}`);
    process.exit(1);
  }

  const author = await prisma.user.findUnique({
    where: { email: args.author },
    select: { id: true, role: true, name: true },
  });
  if (!author) {
    console.error(`İstifadəçi tapılmadı: ${args.author}`);
    process.exit(1);
  }
  if (author.role !== "ARTIST" && author.role !== "ADMIN") {
    console.error(`${args.author} model yükləyə bilməz (rol: ${author.role})`);
    process.exit(1);
  }

  const items = await discover(args.dir);
  if (items.length === 0) {
    console.log("Heç bir model qovluğu tapılmadı.");
    console.log(`Hər model qovluğunda mənbə fayl olmalıdır (${SOURCE_EXT.join(", ")}).`);
    return;
  }

  console.log(`${items.length} model qovluğu tapıldı.\n`);

  let created = 0;
  let skipped = 0;
  let failed = 0;

  for (const item of items) {
    const folderName = path.basename(item.folder);
    const title = item.meta.title ?? titleFromFolder(folderName);
    const baseSlug = slugify(title) || "model";

    try {
      if (item.images.length === 0) {
        console.log(`  ⨯ ${title} — render şəkli yoxdur, buraxıldı`);
        skipped++;
        continue;
      }

      // Təkrar importun qarşısını alır: eyni mənbə faylı ikinci dəfə yazılmır.
      const sourceBuf = await readFile(item.source);
      const sourceHash = createHash("sha256").update(sourceBuf).digest("hex");

      const duplicate = await prisma.asset.findFirst({
        where: { kind: "SOURCE", originalName: path.basename(item.source) },
        select: { model: { select: { slug: true, fileSizeBytes: true } } },
      });
      if (duplicate && Number(duplicate.model.fileSizeBytes) === sourceBuf.length) {
        console.log(`  = ${title} — onsuz da var (${duplicate.model.slug}), buraxıldı`);
        skipped++;
        continue;
      }

      // Unikal slug
      let slug = baseSlug;
      for (let i = 2; await prisma.model.findUnique({ where: { slug } }); i++) {
        slug = `${baseSlug}-${i}`;
      }

      const category = item.categorySlug
        ? await prisma.category.findUnique({
            where: { slug: item.categorySlug },
            select: { id: true, name: true },
          })
        : null;

      if (item.categorySlug && !category) {
        console.log(`  ! ${title} — "${item.categorySlug}" kateqoriyası yoxdur, kateqoriyasız yazılır`);
      }

      if (args.dryRun) {
        console.log(
          `  + ${title}\n` +
            `      slug: ${slug}\n` +
            `      kateqoriya: ${category?.name ?? "—"}\n` +
            `      mənbə: ${path.basename(item.source)} (${(sourceBuf.length / 1024 / 1024).toFixed(1)} MB)\n` +
            `      şəkil: ${item.images.length} · glb: ${item.preview ? "var" : "yox"}`,
        );
        created++;
        continue;
      }

      // --- mənbə fayl: QORUNAN storage-a ---
      const sourceKey = `source/${sourceHash.slice(0, 16)}${path.extname(item.source).toLowerCase()}`;
      await writeFileTo(STORAGE_ROOT, sourceKey, sourceBuf);

      const model = await prisma.model.create({
        data: {
          slug,
          title,
          description: item.meta.description ?? "",
          status: args.publish ? "PUBLISHED" : "PENDING",
          publishedAt: args.publish ? new Date() : null,
          authorId: author.id,
          isOfficial: item.meta.official ?? author.role === "ADMIN",
          categoryId: category?.id ?? null,
          creditCost: MODEL_CREDIT_COST,
          renderer: item.meta.renderer ?? "OTHER",
          formats: (item.meta.formats ?? []).map((f) => f.toLowerCase().replace(/^\./, "")),
          maxVersion: item.meta.maxVersion ?? null,
          polyCount: item.meta.polyCount ?? null,
          vertexCount: item.meta.vertexCount ?? null,
          hasTextures: item.meta.hasTextures ?? false,
          isPbr: item.meta.isPbr ?? false,
          fileSizeBytes: BigInt(sourceBuf.length),
          assets: {
            create: {
              kind: "SOURCE",
              storageKey: sourceKey,
              originalName: path.basename(item.source),
              mimeType: "application/octet-stream",
              sizeBytes: BigInt(sourceBuf.length),
            },
          },
        },
        select: { id: true },
      });

      // --- 3D önizləmə (açıq) ---
      if (item.preview) {
        const buf = await readFile(item.preview);
        const key = `models/${model.id}/preview.glb`;
        await writeFileTo(PUBLIC_UPLOADS, key, buf);
        await prisma.asset.create({
          data: {
            modelId: model.id,
            kind: "PREVIEW_GLB",
            storageKey: key,
            originalName: path.basename(item.preview),
            mimeType: "model/gltf-binary",
            sizeBytes: BigInt(buf.length),
          },
        });
      }

      // --- render şəkilləri (açıq, ölçüsü kiçildilir) ---
      for (const [index, imgPath] of item.images.entries()) {
        const raw = await readFile(imgPath);
        const optimized = await sharp(raw)
          .resize({ width: MAX_IMAGE_WIDTH, withoutEnlargement: true })
          .jpeg({ quality: 84 })
          .toBuffer();

        const key = `models/${model.id}/render-${index}.jpg`;
        await writeFileTo(PUBLIC_UPLOADS, key, optimized);
        await prisma.asset.create({
          data: {
            modelId: model.id,
            kind: "IMAGE",
            storageKey: key,
            originalName: path.basename(imgPath),
            mimeType: "image/jpeg",
            sizeBytes: BigInt(optimized.length),
            sortOrder: index,
          },
        });
      }

      // --- teqlər ---
      for (const name of item.meta.tags ?? []) {
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

      console.log(`  + ${title}  →  /models/${slug}`);
      created++;
    } catch (e) {
      console.log(`  ⨯ ${title} — XƏTA: ${(e as Error).message}`);
      failed++;
    }
  }

  console.log(
    `\nNəticə: ${created} ${args.dryRun ? "yüklənəcək" : "yükləndi"} · ` +
      `${skipped} buraxıldı · ${failed} xəta`,
  );
  if (!args.dryRun && created > 0 && !args.publish) {
    console.log("Modellər moderasiya növbəsindədir — /admin bölməsindən təsdiqləyin.");
  }
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
