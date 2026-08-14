"use client";

import { useRouter, useSearchParams } from "next/navigation";

const SORTS = [
  { value: "new", label: "Ən yeni" },
  { value: "popular", label: "Ən populyar" },
  { value: "cheap", label: "Ən ucuz" },
];

export function SortSelect() {
  const router = useRouter();
  const params = useSearchParams();

  return (
    <label className="flex items-center gap-2 text-sm text-muted">
      Sıralama
      <select
        className="input w-40 py-1.5"
        value={params.get("sort") ?? "new"}
        onChange={(e) => {
          const next = new URLSearchParams(params.toString());
          if (e.target.value === "new") next.delete("sort");
          else next.set("sort", e.target.value);
          next.delete("page");
          router.push(`/models?${next.toString()}`);
        }}
      >
        {SORTS.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  );
}
