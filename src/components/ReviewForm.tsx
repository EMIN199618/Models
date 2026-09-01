"use client";

import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";

import { submitReviewAction } from "@/actions/reviews";

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="btn-primary" disabled={pending}>
      {pending ? "Göndərilir…" : label}
    </button>
  );
}

export function ReviewForm({
  slug,
  initial,
}: {
  slug: string;
  initial?: { rating: number; comment: string };
}) {
  const [state, formAction] = useActionState(submitReviewAction, undefined);
  const [rating, setRating] = useState(initial?.rating ?? 5);
  const [hover, setHover] = useState(0);

  return (
    <form action={formAction} className="card space-y-3 p-4">
      <input type="hidden" name="slug" value={slug} />
      <input type="hidden" name="rating" value={rating} />

      <div>
        <p className="mb-1.5 text-xs text-muted">Reytinqiniz</p>
        <div className="flex gap-1 text-2xl" onMouseLeave={() => setHover(0)}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setRating(n)}
              onMouseEnter={() => setHover(n)}
              className={(hover || rating) >= n ? "text-warning" : "text-border"}
              aria-label={`${n} ulduz`}
            >
              ★
            </button>
          ))}
        </div>
      </div>

      <textarea
        name="comment"
        rows={3}
        maxLength={1000}
        defaultValue={initial?.comment}
        placeholder="Model haqqında fikriniz (istəyə bağlı)…"
        className="input resize-none"
      />

      <div className="flex items-center gap-3">
        <SubmitButton label={initial ? "Rəyi yenilə" : "Rəy göndər"} />
        {state?.ok && <span className="text-xs text-success">Təşəkkürlər — rəyiniz yadda saxlandı</span>}
        {state?.error && <span className="text-xs text-danger">{state.error}</span>}
      </div>
    </form>
  );
}
