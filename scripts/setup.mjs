#!/usr/bin/env node
/**
 * Bir əmrlə quraşdırma: `npm run setup`
 *
 * Windows, macOS və Linux-da eyni işləyir (Node ilə yazılıb, bash deyil).
 *
 * Nə edir:
 *   1. Node versiyasını yoxlayır
 *   2. .env faylı yoxdursa yaradır və təhlükəsiz DOWNLOAD_SECRET generasiya edir
 *   3. Docker varsa PostgreSQL konteynerini qaldırır, yoxsa mövcud bazanı gözləyir
 *   4. Miqrasiyaları tətbiq edir, Prisma client generasiya edir
 *   5. Nümunə məlumatı yükləyir
 */

import { execSync } from "node:child_process";
import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const MIN_NODE_MAJOR = 20;

let step = 0;
const log = (msg) => console.log(`\n[${++step}] ${msg}`);
const ok = (msg) => console.log(`    ✓ ${msg}`);
const warn = (msg) => console.log(`    ! ${msg}`);

function run(command, options = {}) {
  execSync(command, { cwd: ROOT, stdio: "inherit", ...options });
}

function tryRun(command) {
  try {
    execSync(command, { cwd: ROOT, stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function fail(message, hint) {
  console.error(`\n✗ ${message}`);
  if (hint) console.error(`\n  ${hint}`);
  process.exit(1);
}

// --- 1. Node versiyası -----------------------------------------------------

log("Node versiyası yoxlanılır");
const major = Number(process.versions.node.split(".")[0]);
if (major < MIN_NODE_MAJOR) {
  fail(
    `Node ${process.versions.node} çox köhnədir (ən azı ${MIN_NODE_MAJOR} lazımdır).`,
    "https://nodejs.org saytından LTS versiyanı quraşdırın.",
  );
}
ok(`Node ${process.versions.node}`);

// --- 2. .env ---------------------------------------------------------------

log(".env faylı hazırlanır");
const envPath = path.join(ROOT, ".env");
const examplePath = path.join(ROOT, ".env.example");

if (existsSync(envPath)) {
  ok(".env onsuz da mövcuddur — toxunulmadı");
} else {
  if (!existsSync(examplePath)) fail(".env.example tapılmadı.");
  copyFileSync(examplePath, envPath);

  // Placeholder açarı həqiqi təsadüfi dəyərlə əvəz et.
  const secret = randomBytes(32).toString("hex");
  const content = readFileSync(envPath, "utf8").replace(
    /^DOWNLOAD_SECRET=.*$/m,
    `DOWNLOAD_SECRET="${secret}"`,
  );
  writeFileSync(envPath, content);
  ok(".env yaradıldı, DOWNLOAD_SECRET təsadüfi generasiya olundu");
}

// --- 3. Verilənlər bazası --------------------------------------------------

log("PostgreSQL hazırlanır");
const hasDocker = tryRun("docker compose version");

let dockerStarted = false;

if (hasDocker) {
  try {
    run("docker compose up -d");
    dockerStarted = true;
    ok("PostgreSQL konteyneri işə salındı (arxvia-db)");
  } catch {
    // Docker quraşdırılıb, amma işləmir (dayandırılıb, şəbəkə bloklanıb və s.).
    // Bu, dayanmaq üçün səbəb deyil — .env-dəki baza işləyə bilər.
    warn("Docker konteyneri qaldırıla bilmədi — mövcud bazaya cəhd olunacaq");
  }
} else {
  warn("Docker tapılmadı — .env-dəki mövcud bazadan istifadə olunacaq");
}

// Baza cavab verənə qədər gözlə
log("Baza bağlantısı gözlənilir");
const { Client } = await import("pg");
const url = readFileSync(envPath, "utf8").match(/^DATABASE_URL="?([^"\n]+)"?/m)?.[1];
if (!url) fail(".env faylında DATABASE_URL tapılmadı.");

let connected = false;
for (let attempt = 1; attempt <= 30; attempt++) {
  const client = new Client({ connectionString: url });
  try {
    await client.connect();
    await client.end();
    connected = true;
    break;
  } catch {
    await new Promise((r) => setTimeout(r, 1000));
    if (attempt % 5 === 0) console.log(`    …gözlənilir (${attempt}s)`);
  }
}

if (!connected) {
  fail(
    "Verilənlər bazasına 30 saniyə ərzində qoşulmaq mümkün olmadı.",
    dockerStarted
      ? "Konteynerin loglarına baxın: docker compose logs db"
      : [
          "Bunlardan birini edin:",
          "  • Docker Desktop-u işə salıb yenidən cəhd edin: npm run setup",
          "  • Və ya PostgreSQL-i əl ilə qurub .env-dəki DATABASE_URL-i düzəldin",
        ].join("\n  "),
  );
}
ok("Baza cavab verir");

// --- 4. Miqrasiya və client ------------------------------------------------

log("Cədvəllər yaradılır (Prisma migrate)");
run("npx prisma migrate deploy");
ok("Miqrasiyalar tətbiq olundu");

log("Prisma client generasiya olunur");
run("npx prisma generate");
ok("Client hazırdır");

// --- 5. Seed ---------------------------------------------------------------

log("Nümunə məlumat yüklənir");
run("npx tsx prisma/seed.ts");

// --- Nəticə ----------------------------------------------------------------

console.log(`
────────────────────────────────────────────────
  Quraşdırma tamamlandı.

  İşə salmaq üçün:   npm run dev
  Sayt:              http://localhost:3000

  Test hesabları (parol: parol1234)
    admin@arxvia.az        — admin panel
    artist1@arxvia.az      — model yükləmə
    dizayner@example.com   — alıcı, 25 Credit
────────────────────────────────────────────────
`);
