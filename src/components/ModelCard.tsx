import Image from "next/image";
import Link from "next/link";

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
};

const RENDERER_LABEL: Record<string, string> = {
  CORONA: "Corona",
  VRAY: "V-Ray",
  BOTH: "Corona + V-Ray",
  OTHER: "Digər",
};

export function ModelCard({ model }: { model: ModelCardData }) {
  return (
    <article className="card group overflow-hidden transition-colors hover:border-accent/50">
      <Link href={`/models/${model.slug}`} className="block">
        <div className="relative aspect-4/3 bg-surface-2">
          {model.thumbnailUrl ? (
            <Image
              src={model.thumbnailUrl}
              alt={model.title}
              fill
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
              className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-muted">
              Önizləmə yoxdur
            </div>
          )}

          <span className="absolute left-2 top-2 rounded-md bg-black/70 px-2 py-0.5 text-xs font-medium text-white backdrop-blur">
            {model.creditCost === 0 ? "Pulsuz" : `${model.creditCost} Credit`}
          </span>

          {model.isOfficial && (
            <span className="absolute right-2 top-2 rounded-md bg-accent/90 px-2 py-0.5 text-xs font-medium text-white">
              Rəsmi
            </span>
          )}
        </div>
      </Link>

      <div className="p-3">
        <Link href={`/models/${model.slug}`}>
          <h3 className="truncate text-sm font-medium hover:text-accent">{model.title}</h3>
        </Link>

        {/* Müəllif adı yalnız artist modellərində göstərilir */}
        {!model.isOfficial && model.author?.slug && (
          <Link
            href={`/artist/${model.author.slug}`}
            className="mt-0.5 block truncate text-xs text-muted hover:text-accent"
          >
            {model.author.name}
          </Link>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="badge">{RENDERER_LABEL[model.renderer] ?? model.renderer}</span>
          {model.formats.slice(0, 2).map((f) => (
            <span key={f} className="badge uppercase">
              {f}
            </span>
          ))}
          {model.polyCount != null && (
            <span className="badge">{formatPolys(model.polyCount)}</span>
          )}
        </div>
      </div>
    </article>
  );
}

export function formatPolys(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M poly`;
  if (count >= 1_000) return `${Math.round(count / 1_000)}K poly`;
  return `${count} poly`;
}
