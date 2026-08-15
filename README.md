# Arxvia — AI 3D Asset Marketplace (MVP)

3ds Max, Corona Renderer və V-Ray istifadəçiləri üçün 3D model marketplace.
Bu repozitoriya MVP mərhələsidir: **kataloq → 3D önizləmə → Credit ilə alış →
qorunan endirmə** zənciri baş-başa işləyir.

---

## Texnologiyalar

| Sahə | Seçim |
|---|---|
| Framework | Next.js 16 (App Router) + TypeScript |
| Verilənlər bazası | PostgreSQL 16 + Prisma 7 |
| Stil | Tailwind CSS 4 |
| 3D önizləmə | `@google/model-viewer` (`.glb`) |
| Auth | Öz sistemi — bcrypt + DB sessiyası (httpOnly cookie) |
| Fayl saxlama | Lokal disk (S3-ə keçid üçün abstraksiya qatı) |

---

## Quraşdırma

**Lazımdır:** [Node.js 20+](https://nodejs.org) və [Docker Desktop](https://www.docker.com/products/docker-desktop/).
Windows, macOS və Linux-da eyni işləyir.

```bash
git clone https://github.com/EMIN199618/Models.git
cd Models
git checkout claude/3d-model-sales-site-ehmvnh

npm install
npm run setup      # hər şeyi özü qurur
npm run dev
```

Sayt: http://localhost:3000

`npm run setup` avtomatik olaraq: `.env` faylını yaradır və təsadüfi
`DOWNLOAD_SECRET` generasiya edir → PostgreSQL konteynerini qaldırır →
bazanın hazır olmasını gözləyir → miqrasiyaları tətbiq edir → Prisma client
generasiya edir → nümunə məlumatı yükləyir.

### npm 12 və quraşdırma skriptləri

npm 12-dən etibarən paketlərin `postinstall` skriptləri standart olaraq
bloklanır. Prisma və esbuild öz binary fayllarını məhz orada endirdiyi üçün
`npm install`-dan sonra belə bir xəbərdarlıq görsəniz:

```
npm warn allow-scripts 4 packages have install scripts not yet covered
```

bunları işlədin, sonra `npm run setup`-ı təkrarlayın:

```bash
npm approve-scripts --allow-scripts-pending
npm install
```

### Linux qeydləri

İki tipik problem var; skript hər ikisini tanıyıb konkret həll təklif edir:

| Problem | Həll |
|---|---|
| `permission denied … docker.sock` | `sudo usermod -aG docker $USER`, sonra yenidən daxil olun |
| `port is already allocated` (5432) | `sudo systemctl stop postgresql` — və ya mövcud bazadan istifadə edin |

Docker Compose-un həm v2 (`docker compose`), həm də v1 (`docker-compose`)
versiyası dəstəklənir.

### Docker istifadə etmək istəmirsinizsə

PostgreSQL-i özünüz qurun, `.env.example`-ı `.env` kimi kopyalayıb
`DATABASE_URL`-i öz bazanıza yönəldin, sonra yenə `npm run setup` işlədin —
skript Docker olmadığını görüb mövcud bazadan istifadə edəcək.

## Modellərin toplu yüklənməsi

Yüzlərlə modeli bir əmrlə kataloqa yükləmək üçün:

```bash
npm run import -- --dir ./import --author admin@arxvia.az --dry-run   # əvvəlcə yoxla
npm run import -- --dir ./import --author admin@arxvia.az             # moderasiyaya göndər
npm run import -- --dir ./import --author admin@arxvia.az --publish   # dərhal dərc et
```

> Yalnız hüququ sizdə olan modelləri yükləyin — sifarişlə hazırlatdığınız,
> istehsalçıdan aldığınız və ya açıq lisenziyalı (CC0) fayllar.

### Qovluq quruluşu

```
import/
  divan/                        ← kateqoriya slug-ı (avtomatik tanınır)
    modern-boz-divan/           ← model qovluğu (ad başlığa çevrilir)
      model.zip                 ← mənbə fayl (məcburi)
      preview.glb               ← 3D önizləmə (istəyə bağlı)
      01.jpg  02.jpg            ← render şəkilləri (ən azı 1 — məcburi)
      meta.json                 ← metadata (istəyə bağlı)
```

`meta.json` yazılmasa, başlıq qovluq adından, kateqoriya isə valideyn
qovluqdan götürülür.

```json
{
  "title": "Modern boz divan",
  "description": "…",
  "renderer": "CORONA",
  "formats": ["max", "fbx"],
  "maxVersion": "2021",
  "polyCount": 120000,
  "hasTextures": true,
  "isPbr": true,
  "tags": ["divan", "modern"],
  "official": true
}
```

Alət:
- Mənbə faylı **qorunan** storage-a, önizləmələri açıq qovluğa yazır
- Şəkilləri 1600px-ə qədər kiçildib JPEG-ə çevirir
- Təkrar işlədiləndə mövcud modelləri **yenidən yaratmır** (idempotent)
- Şəkli olmayan qovluğu buraxır və səbəbini yazır

### Faydalı əmrlər

| Əmr | Nə edir |
|---|---|
| `npm run dev` | Saytı işə salır |
| `npm run db:up` / `db:down` | Bazanı qaldırır / dayandırır |
| `npm run db:reset` | Bazanı sıfırlayıb nümunə məlumatı yenidən yükləyir |
| `npm run seed` | Yalnız nümunə məlumatı yenidən yükləyir |
| `npm run import -- --dir <qovluq> --author <e-poçt>` | Modelləri toplu yükləyir |
| `npm run e2e` | Alış/endirmə testlərini işlədir (sayt açıq olmalıdır) |
| `npm run pricing` | Qiymət və gəlir bölgüsü testlərini işlədir |
| `npm run build` | İstehsal üçün build |

### Test hesabları

| Rol | E-poçt | Parol | Qeyd |
|---|---|---|---|
| Admin | `admin@arxvia.az` | `parol1234` | Moderasiya, Credit vermə |
| Artist | `artist1@arxvia.az` | `parol1234` | Model yükləmə |
| Alıcı | `dizayner@example.com` | `parol1234` | 150 Credit ilə |

---

## Uçdan-uca yoxlama

Alış və endirmə axınının təhlükəsizliyini yoxlayır (13 test):

```bash
npm run dev      # ayrı terminalda açıq qalsın
npm run e2e
```

Yoxlanan hallar: sessiyasız endirmə, alınmamış model, balansın düzgün
azalması, ledger uyğunluğu, təkrar alışda Credit tutulmaması, balans
çatmayanda geri qaytarma, saxta imzalı token.

---

## Memarlıq — əsas qərarlar

### 1. Satılan fayl heç vaxt birbaşa URL ilə verilmir

Fayllar iki ayrı yerdə saxlanılır:

| | Yer | Giriş |
|---|---|---|
| **Mənbə fayl** (`.max`, `.zip`) | `storage/` — `public/`-dən **kənarda** | Yalnız `/api/download` |
| Preview `.glb`, render şəkilləri | `public/uploads/` | Hamıya açıq |

Endirmə iki addımlıdır:

```
GET /api/download/<modelId>
  → sessiya yoxlanır       (yoxdursa 401)
  → Entitlement yoxlanır   (yoxdursa 403)
  → jurnal yazılır (DownloadLog)
  → 5 dəqiqəlik imzalı token verilir
  → 302 /api/file?token=...

GET /api/file?token=...
  → token yoxlanır (HS256, müddət, user+model+asset bağlantısı)
  → fayl stream olunur
```

Bu quruluş sonradan S3 presigned URL-ə keçidi asanlaşdırır: `/api/file`
əvəzinə birbaşa S3 linki qaytarmaq kifayətdir.

### 2. Credit sistemi ledger üzərində qurulub

`User.creditBalance` sürət üçün saxlanılır, amma **həqiqi mənbə**
`CreditTransaction` jurnalıdır. Balans və jurnal həmişə eyni Prisma
tranzaksiyasında yenilənir (`src/lib/credits.ts`) — yarımçıq əməliyyat
mümkün deyil.

Qaydalar:
- Model bir dəfə alınır, təkrar endirmələr pulsuzdur (`Entitlement` unikal).
- Artist öz modelini pulsuz endirir.
- Balans çatmayanda əməliyyat tam geri qaytarılır.

### 3. Ödəniş şlüzü MVP-də yoxdur — bilərəkdən

Biznes modeli *abunə + Credit* olduğuna görə satış aktı əslində **Credit
tutulmasıdır**. Yəni bütün marketplace ödəniş provayderi olmadan işləyir;
Credit-i hazırda admin verir (`/admin`).

Ödəniş şlüzü sonradan **yalnız bir nöqtəyə** qoşulur: "Credit al / abunə ol".
`Subscription` cədvəli bunun üçün artıq hazırdır.

> Qeyd: Stripe Azərbaycanda dəstəklənmir. Lokal provayderlər (epoint.az,
> Payriff, Kapital/Azericard) araşdırılmalıdır — bu qərar checkout dizaynını
> təyin edir.

### 4. Hər model moderasiyadan keçir

Yeni yüklənən model `PENDING` statusu ilə yaranır və yalnız admin
təsdiqindən sonra kataloqa düşür. Müəllif hüququ şikayəti üçün `/report`
səhifəsi və `Report` cədvəli var — bu nişdə oğurlanmış model ən böyük
praktik riskdir.

---

## Qovluq strukturu

```
prisma/
  schema.prisma        15 cədvəllik data modeli
  seed.ts              nümunə məlumat
  fixtures.ts          .glb və .zip generatorları (xarici asılılıqsız)
scripts/
  setup.mjs            bir əmrlə quraşdırma
  import-models.ts     modellərin toplu yüklənməsi
  e2e-check.ts         alış/endirmə axınının testi
  pricing-check.ts     qiymət və 60/40 bölgüsünün testi
src/
  lib/
    prisma.ts          Prisma client (driver adapter ilə)
    auth.ts            sessiya, parol, rol yoxlamaları
    credits.ts         balans + ledger (tranzaksiyalı)
    storage.ts         fayl saxlama abstraksiyası
    download-token.ts  imzalı endirmə tokenləri
    catalog.ts         axtarış və filtr məntiqi
  actions/             server action-lar (auth, upload, admin, alış)
  app/
    models/            kataloq və model detalı
    studio/            artist paneli
    admin/             moderasiya
    api/download,file  qorunan endirmə
```

---

## Növbəti mərhələlər (MVP-dən sonra)

1. **Kontent strategiyası** — kataloqu doldurmaq marketplace-in ölüm-dirim
   məsələsidir (ilk 2000–5000 model haradan gəlir?).
2. **AI axtarış** — hazırkı axtarış `ILIKE` əsaslıdır. Növbəti addım:
   render şəkillərindən embedding çıxarıb pgvector ilə semantik və
   şəkillə axtarış. Kataloq böyüməmiş bunun dəyəri azdır.
3. **Ödəniş şlüzü** — lokal provayder + `Subscription` axını.
4. **Birbaşa S3 yükləmə** — hazırda fayllar server üzərindən keçir; 500 MB+
   modellər üçün presigned URL lazımdır.
5. **3ds Max plugin** — modeli birbaşa səhnəyə import etmək. Mobil
   tətbiqdən daha güclü rəqabət üstünlüyüdür.
6. Artistə ödəniş (payout), reytinq/rəy, çoxdillilik.
