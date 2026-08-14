"use client";

import { useEffect, useState } from "react";

/**
 * <model-viewer> web komponenti ilə .glb önizləməsi.
 *
 * VACİB: burada göstərilən fayl SATILAN fayl deyil — sadələşdirilmiş
 * preview .glb-dir. Əsl mənbə fayl (.max/.fbx) yalnız Credit xərcləndikdən
 * sonra /api/download vasitəsilə verilir.
 */
export function ModelViewer({
  src,
  poster,
  alt,
}: {
  src: string;
  poster?: string | null;
  alt: string;
}) {
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // Kitabxana yalnız brauzerdə və yalnız lazım olduqda yüklənir.
    import("@google/model-viewer")
      .then(() => {
        if (!cancelled) setReady(true);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <div className="flex aspect-4/3 items-center justify-center rounded-xl border border-border bg-surface-2 text-sm text-muted">
        3D önizləmə yüklənmədi
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="flex aspect-4/3 animate-pulse items-center justify-center rounded-xl border border-border bg-surface-2 text-sm text-muted">
        3D önizləmə yüklənir…
      </div>
    );
  }

  return (
    <model-viewer
      src={src}
      poster={poster ?? undefined}
      alt={alt}
      camera-controls
      touch-action="pan-y"
      shadow-intensity="1"
      exposure="1"
      environment-image="neutral"
      style={{
        width: "100%",
        aspectRatio: "4 / 3",
        borderRadius: "0.75rem",
        border: "1px solid var(--border)",
        background: "var(--surface-2)",
      }}
    />
  );
}
