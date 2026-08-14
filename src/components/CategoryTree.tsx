"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

import type { CategoryTreeNode } from "@/lib/catalog";

/**
 * Sol sidebar-dakı kateqoriya ağacı (3ddd tipli).
 * Valideynə klik → alt kateqoriyalar açılır və o valideynin bütün modelləri
 * göstərilir. Alt kateqoriyaya klik → yalnız onun modelləri.
 */
export function CategoryTree({ tree }: { tree: CategoryTreeNode[] }) {
  const router = useRouter();
  const params = useSearchParams();
  const active = params.get("category");

  // Seçilmiş alt kateqoriyanın valideyni avtomatik açıq olsun.
  const activeParent = tree.find(
    (p) => p.slug === active || p.children.some((c) => c.slug === active),
  );
  const [expanded, setExpanded] = useState<string | null>(activeParent?.slug ?? null);

  const go = useCallback(
    (slug: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (slug) next.set("category", slug);
      else next.delete("category");
      next.delete("page");
      router.push(`/models?${next.toString()}`);
    },
    [params, router],
  );

  return (
    <nav className="text-sm">
      <button
        type="button"
        onClick={() => go(null)}
        className={`mb-1 flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left transition-colors ${
          !active ? "bg-accent/15 font-medium text-accent" : "text-muted hover:bg-surface-2 hover:text-foreground"
        }`}
      >
        Bütün kateqoriyalar
      </button>

      <ul className="space-y-0.5">
        {tree.map((parent) => {
          const isOpen = expanded === parent.slug;
          const isActive = active === parent.slug;

          return (
            <li key={parent.slug}>
              <div className="flex items-stretch">
                <button
                  type="button"
                  onClick={() => go(parent.slug)}
                  className={`flex flex-1 items-center justify-between rounded-lg px-2.5 py-1.5 text-left transition-colors ${
                    isActive
                      ? "bg-accent/15 font-medium text-accent"
                      : "text-foreground hover:bg-surface-2"
                  }`}
                >
                  <span>{parent.name}</span>
                  <span className="text-xs text-muted">{parent.count}</span>
                </button>

                {parent.children.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setExpanded(isOpen ? null : parent.slug)}
                    aria-label={isOpen ? "Bağla" : "Aç"}
                    aria-expanded={isOpen}
                    className="ml-0.5 rounded-lg px-1.5 text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
                  >
                    <span
                      className={`inline-block text-xs transition-transform ${isOpen ? "rotate-90" : ""}`}
                      aria-hidden
                    >
                      ▶
                    </span>
                  </button>
                )}
              </div>

              {isOpen && parent.children.length > 0 && (
                <ul className="mb-1 ml-2.5 border-l border-border pl-2">
                  {parent.children.map((child) => (
                    <li key={child.slug}>
                      <button
                        type="button"
                        onClick={() => go(child.slug)}
                        className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1 text-left transition-colors ${
                          active === child.slug
                            ? "bg-accent/15 font-medium text-accent"
                            : "text-muted hover:bg-surface-2 hover:text-foreground"
                        }`}
                      >
                        <span className="truncate">{child.name}</span>
                        <span className="ml-2 shrink-0 text-xs opacity-70">{child.count}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
