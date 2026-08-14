import Image from "next/image";
import Link from "next/link";

import type { ModelCardData } from "@/components/ModelCard";

/**
 * Yeni yüklənən modellərin sağdan sola sürüşən lenti.
 *
 * Lent CSS animasiyası ilə işləyir (JS taymeri yoxdur) — siyahı iki dəfə
 * render olunur, animasiya -50%-ə çatanda ikinci nüsxə birincinin yerinə
 * düşür və dövr fasiləsiz görünür.
 */
export function NewModelsMarquee({
  models,
  secondsPerItem = 3.5,
}: {
  models: ModelCardData[];
  secondsPerItem?: number;
}) {
  if (models.length === 0) return null;

  // Sürət element sayına bağlıdır ki, az və ya çox modeldə eyni tempdə getsin.
  const duration = models.length * secondsPerItem;

  return (
    <section aria-labelledby="new-models-heading">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 id="new-models-heading" className="text-lg font-semibold">
          Yeni əlavələr
        </h2>
        <Link href="/models" className="text-sm text-accent hover:underline">
          Hamısına bax →
        </Link>
      </div>

      <div className="marquee">
        <ul
          className="marquee-track gap-3"
          style={{ animationDuration: `${duration}s` }}
        >
          {models.map((m) => (
            <MarqueeItem key={m.slug} model={m} />
          ))}
          {/* İkinci nüsxə yalnız vizual dövr üçündür — ekran oxuyucudan gizlədilir */}
          {models.map((m) => (
            <MarqueeItem key={`dup-${m.slug}`} model={m} duplicate />
          ))}
        </ul>
      </div>
    </section>
  );
}

function MarqueeItem({
  model,
  duplicate = false,
}: {
  model: ModelCardData;
  duplicate?: boolean;
}) {
  return (
    <li
      className="w-44 shrink-0 sm:w-52"
      aria-hidden={duplicate || undefined}
      // Dublikat nüsxə klaviatura ilə fokuslanmasın
      inert={duplicate || undefined}
    >
      <Link
        href={`/models/${model.slug}`}
        tabIndex={duplicate ? -1 : undefined}
        className="group block overflow-hidden rounded-lg border border-border bg-surface transition-colors hover:border-accent/60"
      >
        <div className="relative aspect-4/3 bg-surface-2">
          {model.thumbnailUrl ? (
            <Image
              src={model.thumbnailUrl}
              alt={model.title}
              fill
              sizes="208px"
              className="object-cover transition-transform duration-300 group-hover:scale-[1.05]"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-muted">
              Önizləmə yoxdur
            </div>
          )}

          <span
            className={`absolute left-1.5 top-1.5 rounded px-1.5 py-0.5 text-[11px] font-semibold ${
              model.creditCost === 0 ? "bg-success/90 text-white" : "bg-black/70 text-white"
            }`}
          >
            {model.creditCost === 0 ? "Pulsuz" : `${model.creditCost} Cr`}
          </span>
        </div>

        <div className="px-2 py-1.5">
          <span className="block truncate text-xs font-medium">{model.title}</span>
          <span className="block truncate text-[11px] text-muted">
            {model.isOfficial ? "Arxvia" : (model.author?.name ?? "—")}
          </span>
        </div>
      </Link>
    </li>
  );
}
