"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

const RENDERERS = [
  { value: "ALL", label: "Hamısı" },
  { value: "CORONA", label: "Corona" },
  { value: "VRAY", label: "V-Ray" },
  { value: "BOTH", label: "Corona + V-Ray" },
];

const SORTS = [
  { value: "new", label: "Ən yeni" },
  { value: "popular", label: "Ən populyar" },
  { value: "cheap", label: "Ən ucuz" },
];

export function CatalogFilters({
  categories,
  formats,
}: {
  categories: { slug: string; name: string; _count: { models: number } }[];
  formats: string[];
}) {
  const router = useRouter();
  const params = useSearchParams();

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (value === null || value === "" || value === "ALL") next.delete(key);
      else next.set(key, value);
      next.delete("page"); // filtr dəyişəndə birinci səhifəyə qayıt
      router.push(`/models?${next.toString()}`);
    },
    [params, router],
  );

  return (
    <aside className="space-y-5">
      <div>
        <h3 className="label">Kateqoriya</h3>
        <div className="space-y-1">
          <FilterButton
            active={!params.get("category")}
            onClick={() => setParam("category", null)}
            label="Hamısı"
          />
          {categories.map((c) => (
            <FilterButton
              key={c.slug}
              active={params.get("category") === c.slug}
              onClick={() => setParam("category", c.slug)}
              label={c.name}
              count={c._count.models}
            />
          ))}
        </div>
      </div>

      <div>
        <label className="label" htmlFor="renderer">
          Render mühərriki
        </label>
        <select
          id="renderer"
          className="input"
          value={params.get("renderer") ?? "ALL"}
          onChange={(e) => setParam("renderer", e.target.value)}
        >
          {RENDERERS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      {formats.length > 0 && (
        <div>
          <label className="label" htmlFor="format">
            Format
          </label>
          <select
            id="format"
            className="input"
            value={params.get("format") ?? ""}
            onChange={(e) => setParam("format", e.target.value || null)}
          >
            <option value="">Hamısı</option>
            {formats.map((f) => (
              <option key={f} value={f}>
                {f.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      )}

      <div>
        <label className="label" htmlFor="sort">
          Sıralama
        </label>
        <select
          id="sort"
          className="input"
          value={params.get("sort") ?? "new"}
          onChange={(e) => setParam("sort", e.target.value)}
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="accent-[var(--accent)]"
          checked={params.get("free") === "1"}
          onChange={(e) => setParam("free", e.target.checked ? "1" : null)}
        />
        Yalnız pulsuzlar
      </label>
    </aside>
  );
}

function FilterButton({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors ${
        active ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface-2 hover:text-foreground"
      }`}
    >
      <span>{label}</span>
      {count != null && <span className="text-xs opacity-70">{count}</span>}
    </button>
  );
}
