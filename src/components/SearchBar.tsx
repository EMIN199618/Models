"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export function SearchBar({ className = "" }: { className?: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const [value, setValue] = useState(params.get("q") ?? "");

  return (
    <form
      className={`flex gap-2 ${className}`}
      onSubmit={(e) => {
        e.preventDefault();
        const next = new URLSearchParams(params.toString());
        if (value.trim()) next.set("q", value.trim());
        else next.delete("q");
        next.delete("page");
        router.push(`/models?${next.toString()}`);
      }}
    >
      <input
        className="input"
        placeholder="Məsələn: boz velur künc divan"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-label="Model axtar"
      />
      <button type="submit" className="btn-primary shrink-0">
        Axtar
      </button>
    </form>
  );
}
