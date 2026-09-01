/** Salt-oxu ulduz göstəricisi. Yarımçıq ulduz üçün faiz əsaslı clip-path işlədilir. */
export function ReviewStars({ rating, size = "sm" }: { rating: number; size?: "sm" | "md" }) {
  const pct = Math.max(0, Math.min(5, rating)) * 20;
  const cls = size === "md" ? "text-lg" : "text-xs";

  return (
    <span className={`relative inline-flex ${cls} leading-none`} aria-hidden>
      <span className="text-border">★★★★★</span>
      <span
        className="absolute inset-0 overflow-hidden whitespace-nowrap text-warning"
        style={{ width: `${pct}%` }}
      >
        ★★★★★
      </span>
    </span>
  );
}
