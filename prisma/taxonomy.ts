/**
 * Kataloq taksonomiyası — iki səviyyəli (3ddd/3dsky tipli).
 *
 * Valideyn kateqoriya seçiləndə bütün alt kateqoriyaların modelləri göstərilir.
 * Modellər həmişə ALT kateqoriyaya bağlanır.
 */

export type CategoryNode = {
  slug: string;
  name: string;
  children: { slug: string; name: string }[];
};

export const TAXONOMY: CategoryNode[] = [
  {
    slug: "mebel",
    name: "Mebel",
    children: [
      { slug: "divan", name: "Divan" },
      { slug: "kreslo", name: "Kreslo" },
      { slug: "stul", name: "Stul" },
      { slug: "masa", name: "Masa" },
      { slug: "jurnal-masasi", name: "Jurnal masası" },
      { slug: "carpayi", name: "Çarpayı" },
      { slug: "skaf", name: "Şkaf" },
      { slug: "komod", name: "Komod" },
      { slug: "ref", name: "Rəf" },
      { slug: "bar-stulu", name: "Bar stulu" },
      { slug: "skamya", name: "Skamya" },
      { slug: "usaq-mebeli", name: "Uşaq mebeli" },
    ],
  },
  {
    slug: "isiqlandirma",
    name: "İşıqlandırma",
    children: [
      { slug: "cilciraq", name: "Çilçıraq" },
      { slug: "asma-lampa", name: "Asma lampa" },
      { slug: "bra", name: "Bra (divar lampası)" },
      { slug: "dosheme-lampasi", name: "Döşəmə lampası" },
      { slug: "masaustu-lampa", name: "Masaüstü lampa" },
      { slug: "spot", name: "Spot işıqlandırma" },
      { slug: "texniki-isiq", name: "Texniki işıqlandırma" },
    ],
  },
  {
    slug: "dekor",
    name: "Dekor",
    children: [
      { slug: "vaza", name: "Vaza" },
      { slug: "sekil-poster", name: "Şəkil və poster" },
      { slug: "guzgu", name: "Güzgü" },
      { slug: "xalca", name: "Xalça" },
      { slug: "saat", name: "Saat" },
      { slug: "heykelcik", name: "Heykəlcik" },
      { slug: "kitab", name: "Kitab" },
      { slug: "tekstil-perde", name: "Tekstil və pərdə" },
      { slug: "divar-paneli", name: "Divar paneli" },
    ],
  },
  {
    slug: "metbex",
    name: "Mətbəx",
    children: [
      { slug: "metbex-desti", name: "Mətbəx dəsti" },
      { slug: "metbex-texnikasi", name: "Mətbəx texnikası" },
      { slug: "qab-qacaq", name: "Qab-qacaq" },
      { slug: "metbex-qaristirici", name: "Qarışdırıcı" },
    ],
  },
  {
    slug: "santexnika",
    name: "Santexnika",
    children: [
      { slug: "vanna", name: "Vanna" },
      { slug: "dus", name: "Duş kabinası" },
      { slug: "unitaz", name: "Unitaz və bide" },
      { slug: "rakovina", name: "Rakovina" },
      { slug: "qaristirici", name: "Qarışdırıcı" },
      { slug: "vanna-mebeli", name: "Vanna otağı mebeli" },
      { slug: "aksesuar", name: "Aksesuarlar" },
    ],
  },
  {
    slug: "bitkiler",
    name: "Bitkilər",
    children: [
      { slug: "otaq-bitkisi", name: "Otaq bitkisi" },
      { slug: "agac", name: "Ağac" },
      { slug: "cicek", name: "Çiçək" },
      { slug: "qazon-kol", name: "Qazon və kol" },
    ],
  },
  {
    slug: "elektronika",
    name: "Elektronika",
    children: [
      { slug: "tv", name: "Televizor" },
      { slug: "kompyuter", name: "Kompüter" },
      { slug: "audio", name: "Audio texnika" },
      { slug: "meiset-texnikasi", name: "Məişət texnikası" },
    ],
  },
  {
    slug: "qapi-pencere",
    name: "Qapı və pəncərə",
    children: [
      { slug: "qapi", name: "Qapı" },
      { slug: "pencere", name: "Pəncərə" },
      { slug: "pillekan", name: "Pilləkən" },
    ],
  },
  {
    slug: "eksteryer",
    name: "Eksteryer",
    children: [
      { slug: "bag-mebeli", name: "Bağ mebeli" },
      { slug: "kucce-isiqlandirma", name: "Küçə işıqlandırması" },
      { slug: "neqliyyat", name: "Nəqliyyat" },
      { slug: "memarliq", name: "Memarlıq elementləri" },
    ],
  },
  {
    slug: "ofis",
    name: "Ofis",
    children: [
      { slug: "ofis-masasi", name: "Ofis masası" },
      { slug: "ofis-kreslosu", name: "Ofis kreslosu" },
      { slug: "ofis-saxlama", name: "Saxlama sistemləri" },
    ],
  },
];
