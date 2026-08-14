import Image from "next/image";
import Link from "next/link";

import { FavoriteButton } from "@/components/FavoriteButton";

export type ModelCardData = {
  slug: string;
  title: string;
  creditCost: number;
  renderer: string;
  formats: string[];
  polyCount: number | null;
  downloadCount: number;
  isOfficial: boolean;
  thumbnailUrl: string | null;
  author: { name: string; slug: string | null } | null;
  isFavorite?: boolean;
};

const RENDERER_LABEL: Record<string, string> = {
  CORONA: "Corona",
  VRAY: "V-Ray",
  BOTH: "Corona + V-Ray",
  OTHER: "Digər",
};

/**
 * Kataloq kartı — şəkil mərkəzlidir (3ddd/3dsky tipli).
 * Başlıq və texniki məlumat şəklin üstündə, kursor gələndə görünür;
 * toxunmalı cihazlarda isə həmişə görünən alt zolaqda.
 */
export function ModelCard({ model }: { model: ModelCardData }) {
  return (
    <article className="group relative overflow-hidden rounded-lg border border-border bg-surface transition-colors hover:border-accent/60">
      <Link href={`/models/${model.slug}`} className="block">
        <div className="relative aspect-4/3 bg-surface-2">
          {model.thumbnailUrl ? (
            <Image
              src={model.thumbnailUrl}
              alt={model.title}
              fill
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
              className="object-cover transition-transform duration-300 group-hover:scale-[1.04]"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-muted">
              Önizləmə yoxdur
            </div>
          )}

          {/* Qiymət nişanı */}
          <span
            className={`absolute left-2 top-2 rounded px-1.5 py-0.5 text-[11px] font-semibold backdrop-blur ${
              model.creditCost === 0
                ? "bg-success/90 text-white"
                : "bg-black/70 text-white"
            }`}
          >
            {model.creditCost === 0 ? "Pulsuz" : `${model.creditCost} Cr`}
          </span>

          {model.isOfficial && (
            <span className="absolute right-2 top-2 rounded bg-accent/90 px-1.5 py-0.5 text-[11px] font-semibold text-white">
              Rəsmi
            </span>
          )}

          {/* Hover məlumat zolağı */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent p-2.5 pt-8 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
            <h3 className="truncate text-xs font-medium text-white">{model.title}</h3>
            <div className="mt-1 flex items-center gap-1.5 text-[10px] text-white/70">
              <span>{RENDERER_LABEL[model.renderer] ?? model.renderer}</span>
              {model.formats[0] && <span>· {model.formats[0].toUpperCase()}</span>}
              {model.polyCount != null && <span>· {formatPolys(model.polyCount)}</span>}
              <span className="ml-auto">↓ {model.downloadCount}</span>
            </div>
          </div>
        </div>
      </Link>

      {/* Seçilmişlər düyməsi — Link-dən kənarda ki, klik keçidi tetikləməsin */}
      <div className="absolute bottom-2 right-2 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <FavoriteButton slug={model.slug} initial={model.isFavorite ?? false} />
      </div>

      {/* Toxunmalı cihazlar və oxunaqlılıq üçün daimi alt sətir */}
      <div className="px-2 py-1.5">
        <Link
          href={`/models/${model.slug}`}
          className="block truncate text-xs font-medium hover:text-accent"
        >
          {model.title}
        </Link>
        {!model.isOfficial && model.author?.slug ? (
          <Link
            href={`/artist/${model.author.slug}`}
            className="block truncate text-[11px] text-muted hover:text-accent"
          >
            {model.author.name}
          </Link>
        ) : (
          <span className="block truncate text-[11px] text-muted">Arxvia</span>
        )}
      </div>
    </article>
  );
}

export function formatPolys(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M poly`;
  if (count >= 1_000) return `${Math.round(count / 1_000)}K poly`;
  return `${count} poly`;
}
