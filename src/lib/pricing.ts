/**
 * QİYMƏT QAYDALARI — hamısı bir yerdə.
 *
 * Qiyməti dəyişmək lazım gələndə yalnız bu fayla toxunun; qalan kod
 * bu sabitlərdən istifadə edir.
 */

/** Bir modelin endirilməsi neçə Credit-ə başa gəlir. Pulsuz model yoxdur. */
export const MODEL_CREDIT_COST = 10;

/** Artistin payı. Qalanı platformanındır (60/40). */
export const ARTIST_REVENUE_SHARE = 0.6;

/** Dostunu dəvət edən kodu daxil edən yeni istifadəçiyə verilən bonus. */
export const REFERRAL_BONUS_CREDITS = 200;

/**
 * Bonusun nə vaxt veriləcəyi.
 *
 *  "REGISTRATION"    — kod daxil edilən kimi (hazırkı seçim)
 *  "FIRST_PURCHASE"  — yeni istifadəçi ilk Credit paketini alandan sonra
 *
 * DİQQƏT: "REGISTRATION" variantında hər yeni hesab 200 Credit = 20 model
 * pulsuz alır. Saxta hesablarla sui-istifadə mümkündür. Sayt böyüyəndə
 * "FIRST_PURCHASE"-ə keçirmək tövsiyə olunur — burada bir sətir dəyişir.
 */
export const REFERRAL_BONUS_TRIGGER: "REGISTRATION" | "FIRST_PURCHASE" = "REGISTRATION";

export type CreditPackage = {
  id: string;
  name: string;
  credits: number;
  /** Qiymət qəpiklə — kəsr xətalarının qarşısını almaq üçün tam ədəd. */
  priceMinor: number;
  currency: string;
  /** Kataloqda vurğulanan paket */
  featured?: boolean;
};

export const CREDIT_PACKAGES: CreditPackage[] = [
  {
    id: "start",
    name: "Start",
    credits: 1000,
    priceMinor: 1500, // 15.00 AZN
    currency: "AZN",
  },
  {
    id: "plus",
    name: "Plus",
    credits: 1500,
    priceMinor: 2000, // 20.00 AZN
    currency: "AZN",
    featured: true,
  },
  {
    id: "pro",
    name: "Pro",
    credits: 2500,
    priceMinor: 3000, // 30.00 AZN
    currency: "AZN",
  },
];

export function findPackage(id: string): CreditPackage | undefined {
  return CREDIT_PACKAGES.find((p) => p.id === id);
}

/**
 * Artist ödənişləri üçün istinad kursu: 1 Credit neçə AZN-dir.
 *
 * Credit müxtəlif paketlərdən müxtəlif qiymətə alınır, ona görə qazancı
 * hesablamaq üçün vahid istinad lazımdır. Ən baza paketin kursu götürülür —
 * bu, artistin ziyanına olmayan, ehtiyatlı seçimdir.
 */
export const CREDIT_REFERENCE_MINOR =
  CREDIT_PACKAGES[0].priceMinor / CREDIT_PACKAGES[0].credits;

/** Credit-in pul dəyəri (qəpiklə). */
export function creditsToMinor(credits: number): number {
  return Math.round(credits * CREDIT_REFERENCE_MINOR);
}

/**
 * 1000 → "1 000".
 *
 * `toLocaleString` istifadə OLUNMUR: Node və brauzer eyni locale üçün fərqli
 * ayırıcı verə bilər, bu da server/klient uyğunsuzluğuna (hydration xətası)
 * gətirib çıxarır. Bu funksiya hər iki tərəfdə eyni nəticəni qaytarır.
 */
export function formatCredits(value: number): string {
  return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
}

/** 1500 → "15.00 AZN" */
export function formatMinor(minor: number, currency = "AZN"): string {
  return `${(minor / 100).toFixed(2)} ${currency}`;
}

/** Bir alışdan artistə düşən Credit sayı. */
export function artistShareOf(credits: number): number {
  return Math.round(credits * ARTIST_REVENUE_SHARE);
}

/** Paketdə bir modelin faktiki qiyməti — "1 model ≈ 0.15 AZN". */
export function pricePerModel(pkg: CreditPackage): number {
  return (pkg.priceMinor / pkg.credits) * MODEL_CREDIT_COST;
}
