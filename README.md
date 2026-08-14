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

```bash
# 1. Asılılıqlar
npm install

# 2. PostgreSQL bazası
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER marketplace WITH PASSWORD 'marketplace' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE marketplace OWNER marketplace;"

# 3. .env faylı
cp .env.example .env      # sonra DOWNLOAD_SECRET dəyərini dəyişin

# 4. Miqrasiya və Prisma client
npx prisma migrate dev
npx prisma generate

# 5. Nümunə məlumat (8 model, 4 istifadəçi, şəkillər və .glb fayllar)
npm run seed

# 6. İşə sal
npm run dev
```

Sayt: http://localhost:3000

### Test hesabları

| Rol | E-poçt | Parol | Qeyd |
|---|---|---|---|
| Admin | `admin@arxvia.az` | `parol1234` | Moderasiya, Credit vermə |
| Artist | `artist1@arxvia.az` | `parol1234` | Model yükləmə |
| Alıcı | `dizayner@example.com` | `parol1234` | 25 Credit ilə |

---

## Uçdan-uca yoxlama

Alış və endirmə axınının təhlükəsizliyini yoxlayır (13 test):

```bash
npm run dev          # ayrı terminalda
npx tsx scripts/e2e-check.ts
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
  schema.prisma        13 cədvəllik data modeli
  seed.ts              nümunə məlumat
  fixtures.ts          .glb və .zip generatorları (xarici asılılıqsız)
scripts/
  e2e-check.ts         alış/endirmə axınının testi
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
