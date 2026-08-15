import "dotenv/config";

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

import bcrypt from "bcryptjs";
import sharp from "sharp";
import { PrismaPg } from "@prisma/adapter-pg";

import { PrismaClient } from "../src/generated/prisma/client.js";
import { makeBoxGlb, makeZip } from "./fixtures.js";
import { TAXONOMY } from "./taxonomy.js";
import {
  CREDIT_VALIDITY_DAYS,
  MODEL_CREDIT_COST,
  REFERRAL_BONUS_CREDITS,
} from "../src/lib/pricing.js";

const prisma = new PrismaClient({
  adapter: new PrismaPg({ connectionString: process.env.DATABASE_URL! }),
});

const PUBLIC_UPLOADS = path.resolve("./public/uploads");
const STORAGE_ROOT = path.resolve(process.env.STORAGE_ROOT ?? "./storage");

// ---------------------------------------------------------------------------

type SeedModel = {
  title: string;
  description: string;
  category: string;
  renderer: "CORONA" | "VRAY" | "BOTH";
  formats: string[];
  maxVersion: string;
  polyCount: number;
  vertexCount: number;
  isPbr: boolean;
  tags: string[];
  box: { x: number; y: number; z: number };
  color: [number, number, number];
  official: boolean;
  artist: number; // artist indeksi
};

const MODELS: SeedModel[] = [
  {
    title: "Modul künc divan — velur",
    description:
      "Üç modullu künc divan. Velur teksturaları 4K həllində, Corona materialları hazır vəziyyətdə qurulub.\nÖlçülər: 320 × 210 × 85 sm.",
    category: "divan",
    renderer: "CORONA",
    formats: ["max", "fbx"],
    maxVersion: "2021",
    polyCount: 184_500,
    vertexCount: 96_200,
    isPbr: true,
    tags: ["divan", "künc divan", "velur", "modern"],
    box: { x: 3.2, y: 0.85, z: 2.1 },
    color: [0.42, 0.45, 0.55],
    official: true,
    artist: 0,
  },
  {
    title: "Skandinav yemək masası — palıd",
    description:
      "Təbii palıd örtüklü yemək masası, 6 nəfərlik. V-Ray və Corona üçün ayrı material dəstləri daxildir.",
    category: "masa",
    renderer: "BOTH",
    formats: ["max", "fbx", "obj"],
    maxVersion: "2020",
    polyCount: 42_800,
    vertexCount: 23_100,
    isPbr: true,
    tags: ["masa", "palıd", "skandinav", "yemək otağı"],
    box: { x: 1.8, y: 0.75, z: 0.9 },
    color: [0.65, 0.48, 0.3],
    official: true,
    artist: 0,
  },
  {
    title: "Asma çilçıraq — mis borular",
    description:
      "12 lampalı dekorativ asma çilçıraq. IES işıq profili faylı arxivə daxildir.",
    category: "cilciraq",
    renderer: "CORONA",
    formats: ["max"],
    maxVersion: "2022",
    polyCount: 96_400,
    vertexCount: 51_800,
    isPbr: true,
    tags: ["çilçıraq", "işıq", "mis", "loft"],
    box: { x: 0.9, y: 1.2, z: 0.9 },
    color: [0.72, 0.45, 0.2],
    official: false,
    artist: 1,
  },
  {
    title: "Kitab rəfi — metal karkas",
    description: "Beş səviyyəli açıq kitab rəfi. Aşağı poliqonlu, səhnə üçün optimallaşdırılıb.",
    category: "ref",
    renderer: "VRAY",
    formats: ["max", "fbx"],
    maxVersion: "2019",
    polyCount: 18_900,
    vertexCount: 11_400,
    isPbr: false,
    tags: ["rəf", "kitab rəfi", "metal", "loft"],
    box: { x: 1.6, y: 2.0, z: 0.35 },
    color: [0.28, 0.3, 0.34],
    official: false,
    artist: 1,
  },
  {
    title: "Akrilik vanna — ayaqlı",
    description: "Sərbəst dayanan ayaqlı vanna. Su səthi üçün ayrıca material daxildir.",
    category: "vanna",
    renderer: "CORONA",
    formats: ["max", "obj"],
    maxVersion: "2021",
    polyCount: 64_200,
    vertexCount: 33_700,
    isPbr: true,
    tags: ["vanna", "santexnika", "klassik"],
    box: { x: 1.7, y: 0.65, z: 0.8 },
    color: [0.88, 0.88, 0.9],
    official: false,
    artist: 2,
  },
  {
    title: "Dekorativ vaza dəsti (3 ədəd)",
    description: "Üç ədədlik keramik vaza dəsti. Masaüstü və döşəmə variantları daxildir.",
    category: "vaza",
    renderer: "BOTH",
    formats: ["max", "fbx", "obj"],
    maxVersion: "2020",
    polyCount: 12_400,
    vertexCount: 7_200,
    isPbr: true,
    tags: ["vaza", "dekor", "keramika", "masaüstü"],
    box: { x: 0.6, y: 0.5, z: 0.35 },
    color: [0.85, 0.8, 0.72],
    official: true,
    artist: 0,
  },
  {
    title: "Ofis kreslosu — tor arxalıq",
    description: "Erqonomik ofis kreslosu, hərəkət edən hissələri ayrı obyektlərdir.",
    category: "ofis-kreslosu",
    renderer: "VRAY",
    formats: ["max", "fbx"],
    maxVersion: "2022",
    polyCount: 88_600,
    vertexCount: 47_300,
    isPbr: true,
    tags: ["kreslo", "ofis", "erqonomik"],
    box: { x: 0.7, y: 1.2, z: 0.7 },
    color: [0.18, 0.2, 0.24],
    official: false,
    artist: 2,
  },
  {
    title: "Divar panelləri — reyka (parametrik)",
    description: "Şaquli taxta reyka divar paneli. Uzunluğu asanlıqla dəyişdirilə bilər.",
    category: "divar-paneli",
    renderer: "CORONA",
    formats: ["max"],
    maxVersion: "2021",
    polyCount: 24_800,
    vertexCount: 15_600,
    isPbr: true,
    tags: ["divar paneli", "reyka", "taxta", "akustik"],
    box: { x: 2.4, y: 2.7, z: 0.06 },
    color: [0.55, 0.38, 0.24],
    official: false,
    artist: 1,
  },
];

// ---------------------------------------------------------------------------

/**
 * Hər alt kateqoriya üçün nümunə model generasiya edir.
 * Məqsəd: kataloqun, filtrlərin və səhifələmənin real şəraitdə görünməsi.
 */
function generateFillerModels(): SeedModel[] {
  const STYLES = [
    "Modern",
    "Klassik",
    "Skandinav",
    "Loft",
    "Minimalist",
    "Neoklassik",
    "Art Deco",
    "Provans",
    "Yapon",
    "İndustrial",
  ];
  const MATERIALS = ["palıd", "qoz ağacı", "metal", "mərmər", "keramika", "parça", "şüşə", "mis"];
  const PALETTE: [number, number, number][] = [
    [0.42, 0.45, 0.55],
    [0.65, 0.48, 0.3],
    [0.72, 0.45, 0.2],
    [0.28, 0.3, 0.34],
    [0.85, 0.8, 0.72],
    [0.55, 0.38, 0.24],
    [0.35, 0.42, 0.38],
    [0.78, 0.72, 0.62],
    [0.5, 0.24, 0.24],
    [0.2, 0.28, 0.4],
  ];
  const RENDERERS = ["CORONA", "VRAY", "BOTH"] as const;
  const FORMAT_SETS = [
    ["max"],
    ["max", "fbx"],
    ["max", "fbx", "obj"],
    ["max", "obj"],
  ];
  const VERSIONS = ["2018", "2019", "2020", "2021", "2022"];

  // Determinist seçim — seed hər dəfə eyni nəticəni versin.
  let counter = 0;
  const pick = <T,>(arr: readonly T[]): T => arr[counter++ % arr.length];

  const out: SeedModel[] = [];

  for (const parent of TAXONOMY) {
    for (const child of parent.children) {
      const style = pick(STYLES);
      const material = pick(MATERIALS);
      const poly = 8_000 + ((counter * 7919) % 240_000);

      out.push({
        title: `${style} ${child.name.toLowerCase()} — ${material}`,
        description:
          `${child.name} modeli, ${style.toLowerCase()} üslubda. Materiallar ` +
          `${material} əsasındadır və render mühərriki üçün hazır qurulub.\n` +
          `Səhnəyə birbaşa import edilə bilər.`,
        category: child.slug,
        renderer: pick(RENDERERS),
        formats: pick(FORMAT_SETS),
        maxVersion: pick(VERSIONS),
        polyCount: poly,
        vertexCount: Math.round(poly * 0.55),
        isPbr: counter % 3 !== 0,
        tags: [child.name.toLowerCase(), style.toLowerCase(), material, parent.name.toLowerCase()],
        box: {
          x: 0.4 + ((counter * 13) % 25) / 10,
          y: 0.4 + ((counter * 7) % 22) / 10,
          z: 0.3 + ((counter * 11) % 18) / 10,
        },
        color: pick(PALETTE),
        // Rəsmi modellərin müəllifi həmişə platformanın öz hesabıdır (indeks 0).
        official: counter % 4 === 0,
        artist: counter % 4 === 0 ? 0 : 1 + (counter % 2),
      });
    }
  }

  return out;
}

/** Render şəkli imitasiyası — qradiyent fon + obyektin siluети. */
async function makeRenderImage(
  title: string,
  color: [number, number, number],
  variant: number,
): Promise<Buffer> {
  const w = 1200;
  const h = 900;
  const [r, g, b] = color.map((c) => Math.round(c * 255));
  const bgTop = variant % 2 === 0 ? "#1b1f29" : "#232833";
  const bgBottom = variant % 2 === 0 ? "#0e1116" : "#151922";

  const svg = `
    <svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${bgTop}"/>
          <stop offset="100%" stop-color="${bgBottom}"/>
        </linearGradient>
        <linearGradient id="obj" x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0%" stop-color="rgb(${Math.min(255, r + 35)},${Math.min(255, g + 35)},${Math.min(255, b + 35)})"/>
          <stop offset="100%" stop-color="rgb(${Math.round(r * 0.55)},${Math.round(g * 0.55)},${Math.round(b * 0.55)})"/>
        </linearGradient>
        <radialGradient id="shadow" cx="0.5" cy="0.5">
          <stop offset="0%" stop-color="rgba(0,0,0,0.55)"/>
          <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
        </radialGradient>
      </defs>
      <rect width="${w}" height="${h}" fill="url(#bg)"/>
      <ellipse cx="${w / 2}" cy="${h * 0.74}" rx="${w * 0.3}" ry="${h * 0.06}" fill="url(#shadow)"/>
      <rect x="${w * 0.28}" y="${h * 0.32 + variant * 8}" width="${w * 0.44}" height="${h * 0.38}"
            rx="18" fill="url(#obj)"/>
      <rect x="${w * 0.28}" y="${h * 0.32 + variant * 8}" width="${w * 0.44}" height="${h * 0.09}"
            rx="18" fill="rgba(255,255,255,0.09)"/>
      <text x="40" y="${h - 40}" font-family="sans-serif" font-size="26" fill="rgba(255,255,255,0.35)">
        ${title.replace(/[<&>]/g, "")} · görünüş ${variant + 1}
      </text>
    </svg>`;

  return sharp(Buffer.from(svg)).jpeg({ quality: 82 }).toBuffer();
}

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

async function writePublic(key: string, data: Buffer): Promise<void> {
  const full = path.resolve(PUBLIC_UPLOADS, key);
  await mkdir(path.dirname(full), { recursive: true });
  await writeFile(full, data);
}

async function writeStorage(key: string, data: Buffer): Promise<void> {
  const full = path.resolve(STORAGE_ROOT, key);
  await mkdir(path.dirname(full), { recursive: true });
  await writeFile(full, data);
}

// ---------------------------------------------------------------------------

async function main() {
  console.log("Seed başlayır…");

  // Təmiz başlanğıc
  await prisma.$transaction([
    prisma.downloadLog.deleteMany(),
    prisma.creditTransaction.deleteMany(),
    prisma.entitlement.deleteMany(),
    prisma.favorite.deleteMany(),
    prisma.report.deleteMany(),
    prisma.modelTag.deleteMany(),
    prisma.asset.deleteMany(),
    prisma.model.deleteMany(),
    prisma.tag.deleteMany(),
    prisma.subscription.deleteMany(),
    prisma.session.deleteMany(),
    prisma.category.deleteMany(),
    prisma.user.deleteMany(),
  ]);

  // --- kateqoriyalar (iki səviyyəli ağac) ---
  let subCount = 0;
  for (const [pIndex, parent] of TAXONOMY.entries()) {
    const created = await prisma.category.create({
      data: { slug: parent.slug, name: parent.name, sortOrder: pIndex },
    });
    for (const [cIndex, child] of parent.children.entries()) {
      await prisma.category.create({
        data: {
          slug: child.slug,
          name: child.name,
          parentId: created.id,
          sortOrder: cIndex,
        },
      });
      subCount++;
    }
  }
  console.log(`  ${TAXONOMY.length} əsas + ${subCount} alt kateqoriya`);

  // --- istifadəçilər ---
  const password = await bcrypt.hash("parol1234", 12);

  const admin = await prisma.user.create({
    data: {
      email: "admin@arxvia.az",
      passwordHash: password,
      name: "Arxvia Studio",
      role: "ADMIN",
      slug: "arxvia-studio",
      bio: "Platformanın rəsmi kolleksiyası.",
      country: "Azərbaycan",
      creditBalance: 0,
    },
  });

  const artists = await Promise.all(
    [
      { name: "Kamran Əliyev", bio: "İnteryer vizualizatoru, 8 illik təcrübə.", country: "Azərbaycan" },
      { name: "Leyla Hüseynova", bio: "Mebel modelləşdirmə üzrə 3D artist.", country: "Azərbaycan" },
    ].map((a, i) =>
      prisma.user.create({
        data: {
          email: `artist${i + 1}@arxvia.az`,
          passwordHash: password,
          name: a.name,
          role: "ARTIST",
          slug: slugify(a.name),
          bio: a.bio,
          country: a.country,
          creditBalance: 0,
        },
      }),
    ),
  );

  const buyer = await prisma.user.create({
    data: {
      email: "dizayner@example.com",
      passwordHash: password,
      name: "Nigar Məmmədova",
      role: "USER",
      creditBalance: 0,
    },
  });

  // Başlanğıc Credit-lər (ledger ilə birlikdə)
  for (const [user, amount, reason] of [
    [buyer, 150, "CREDIT_PACKAGE"],
    [artists[0], REFERRAL_BONUS_CREDITS, "REFERRAL"],
    [artists[1], REFERRAL_BONUS_CREDITS, "REFERRAL"],
  ] as const) {
    await prisma.user.update({
      where: { id: user.id },
      data: { creditBalance: amount },
    });
    await prisma.creditTransaction.create({
      data: {
        userId: user.id,
        amount,
        reason,
        balanceAfter: amount,
        note: "Seed",
        remaining: amount,
        expiresAt: new Date(Date.now() + CREDIT_VALIDITY_DAYS * 24 * 60 * 60 * 1000),
      },
    });
  }
  console.log("  4 istifadəçi (1 admin, 2 artist, 1 alıcı)");

  // --- modellər ---
  const authors = [admin, ...artists];

  // Kataloq boş görünməsin deyə hər alt kateqoriyaya nümunə modellər.
  const allModels = [...MODELS, ...generateFillerModels()];

  for (const [index, m] of allModels.entries()) {
    const category = await prisma.category.findUnique({ where: { slug: m.category } });
    const author = authors[m.artist];

    // Mənbə faylı — QORUNAN storage-a (public-dən kənar)
    const zip = makeZip(
      "OXU-MENI.txt",
      [
        `${m.title}`,
        "",
        "Bu, seed məlumatı üçün yaradılmış nümunə arxivdir.",
        "Real layihədə burada .max faylı və teksturalar olur.",
        `Format: ${m.formats.join(", ")}`,
        `3ds Max: ${m.maxVersion}`,
      ].join("\n"),
    );
    const sourceKey = `source/${randomUUID()}.zip`;
    await writeStorage(sourceKey, zip);

    const model = await prisma.model.create({
      data: {
        slug: slugify(m.title),
        title: m.title,
        description: m.description,
        status: "PUBLISHED",
        publishedAt: new Date(Date.now() - index * 36e5),
        authorId: author.id,
        isOfficial: m.official,
        categoryId: category?.id ?? null,
        creditCost: MODEL_CREDIT_COST,
        renderer: m.renderer,
        formats: m.formats,
        maxVersion: m.maxVersion,
        polyCount: m.polyCount,
        vertexCount: m.vertexCount,
        hasTextures: true,
        isPbr: m.isPbr,
        fileSizeBytes: BigInt(zip.length),
        downloadCount: Math.floor(Math.random() * 40),
        viewCount: Math.floor(Math.random() * 400),
        assets: {
          create: {
            kind: "SOURCE",
            storageKey: sourceKey,
            originalName: `${slugify(m.title)}.zip`,
            mimeType: "application/zip",
            sizeBytes: BigInt(zip.length),
          },
        },
      },
    });

    // 3D önizləmə (.glb) — açıq
    const glb = makeBoxGlb(m.box, m.color);
    const glbKey = `models/${model.id}/preview.glb`;
    await writePublic(glbKey, glb);
    await prisma.asset.create({
      data: {
        modelId: model.id,
        kind: "PREVIEW_GLB",
        storageKey: glbKey,
        originalName: "preview.glb",
        mimeType: "model/gltf-binary",
        sizeBytes: BigInt(glb.length),
      },
    });

    // Render şəkilləri — açıq
    // Detallı modellərdə 3, generasiya olunanlarda 2 render şəkli.
    const imageCount = index < MODELS.length ? 3 : 2;
    for (let v = 0; v < imageCount; v++) {
      const img = await makeRenderImage(m.title, m.color, v);
      const key = `models/${model.id}/render-${v}.jpg`;
      await writePublic(key, img);
      await prisma.asset.create({
        data: {
          modelId: model.id,
          kind: "IMAGE",
          storageKey: key,
          originalName: `render-${v}.jpg`,
          mimeType: "image/jpeg",
          sizeBytes: BigInt(img.length),
          sortOrder: v,
        },
      });
    }

    // Teqlər
    for (const name of m.tags) {
      const tag = await prisma.tag.upsert({
        where: { slug: slugify(name) },
        create: { slug: slugify(name), name },
        update: {},
      });
      await prisma.modelTag.create({ data: { modelId: model.id, tagId: tag.id } });
    }

    if (index < MODELS.length) console.log(`  model: ${m.title}`);
    else if (index === MODELS.length) {
      console.log(`  + ${allModels.length - MODELS.length} nümunə model generasiya olunur…`);
    }
  }

  // --- moderasiya növbəsində bir model (admin panelini yoxlamaq üçün) ---
  const pendingZip = makeZip("OXU-MENI.txt", "Moderasiya gözləyən nümunə model.");
  const pendingKey = `source/${randomUUID()}.zip`;
  await writeStorage(pendingKey, pendingZip);

  const pendingModel = await prisma.model.create({
    data: {
      slug: "jurnal-masasi-mermer",
      title: "Jurnal masası — mərmər səth",
      description: "Mərmər səthli jurnal masası, qara metal ayaqlar.",
      status: "PENDING",
      authorId: artists[1].id,
      renderer: "CORONA",
      formats: ["max", "fbx"],
      maxVersion: "2021",
      polyCount: 31_200,
      hasTextures: true,
      isPbr: true,
      fileSizeBytes: BigInt(pendingZip.length),
      assets: {
        create: {
          kind: "SOURCE",
          storageKey: pendingKey,
          originalName: "jurnal-masasi.zip",
          mimeType: "application/zip",
          sizeBytes: BigInt(pendingZip.length),
        },
      },
    },
  });

  const pendingImg = await makeRenderImage("Jurnal masası", [0.75, 0.75, 0.78], 0);
  const pendingImgKey = `models/${pendingModel.id}/render-0.jpg`;
  await writePublic(pendingImgKey, pendingImg);
  await prisma.asset.create({
    data: {
      modelId: pendingModel.id,
      kind: "IMAGE",
      storageKey: pendingImgKey,
      originalName: "render-0.jpg",
      mimeType: "image/jpeg",
      sizeBytes: BigInt(pendingImg.length),
    },
  });
  console.log("  moderasiyada: Jurnal masası");

  console.log("\nSeed tamamlandı.");
  console.log("  admin@arxvia.az / parol1234        (ADMIN)");
  console.log("  artist1@arxvia.az / parol1234      (ARTIST)");
  console.log("  dizayner@example.com / parol1234   (USER, 150 Credit)");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
