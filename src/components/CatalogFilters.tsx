"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import { CategoryTree } from "@/components/CategoryTree";
import type { CategoryTreeNode } from "@/lib/catalog";

const RENDERERS = [
  { value: "ALL", label: "Hamısı" },
  { value: "CORONA", label: "Corona" },
  { value: "VRAY", label: "V-Ray" },
  { value: "BOTH", label: "Corona + V-Ray" },
];

export function CatalogFilters({
  tree,
  formats,
}: {
  tree: CategoryTreeNode[];
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

  const hasFilters =
    params.get("category") ||
    params.get("renderer") ||
    params.get("format") ||
    params.get("free") ||
    params.get("q");

  return (
    <aside className="space-y-6">
      <div>
        <h3 className="label">Kateqoriyalar</h3>
        <CategoryTree tree={tree} />
      </div>

      <div className="space-y-4 border-t border-border pt-5">
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

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="accent-[var(--accent)]"
            checked={params.get("free") === "1"}
            onChange={(e) => setParam("free", e.target.checked ? "1" : null)}
          />
          Yalnız pulsuzlar
        </label>

        {hasFilters && (
          <button
            type="button"
            onClick={() => router.push("/models")}
            className="text-xs text-muted underline-offset-2 hover:text-accent hover:underline"
          >
            Bütün filtrləri sıfırla
          </button>
        )}
      </div>
    </aside>
  );
}
