import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export const metadata = { title: "Şikayət" };

/**
 * Müəllif hüququ / keyfiyyət şikayəti.
 * Marketplace üçün hüquqi minimumun bir hissəsidir — silinmə prosesinin girişi.
 */
async function submitReport(formData: FormData): Promise<void> {
  "use server";

  const slug = String(formData.get("slug") ?? "");
  const reason = String(formData.get("reason") ?? "");
  const details = String(formData.get("details") ?? "").slice(0, 2000);
  if (!slug || !reason) return;

  const [model, user] = await Promise.all([
    prisma.model.findUnique({ where: { slug }, select: { id: true } }),
    getCurrentUser(),
  ]);
  if (!model) return;

  await prisma.report.create({
    data: {
      modelId: model.id,
      reporterId: user?.id ?? null,
      reason,
      details,
    },
  });

  redirect(`/models/${slug}?reported=1`);
}

export default async function ReportPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const slug = typeof params.model === "string" ? params.model : "";

  const model = slug
    ? await prisma.model.findUnique({
        where: { slug },
        select: { title: true, slug: true },
      })
    : null;

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-1 text-2xl font-semibold">Şikayət göndər</h1>
      <p className="mb-6 text-sm text-muted">
        {model
          ? `Model: ${model.title}`
          : "Şikayət etmək istədiyiniz modelin səhifəsindən keçid edin."}
      </p>

      {model && (
        <form action={submitReport} className="card space-y-4 p-5">
          <input type="hidden" name="slug" value={model.slug} />

          <div>
            <label className="label" htmlFor="reason">
              Səbəb
            </label>
            <select id="reason" name="reason" className="input" required>
              <option value="COPYRIGHT">Müəllif hüququ pozuntusu</option>
              <option value="STOLEN">Başqa saytdan oğurlanıb</option>
              <option value="QUALITY">Keyfiyyət / təsvirə uyğunsuzluq</option>
              <option value="SPAM">Spam və ya zərərli məzmun</option>
            </select>
          </div>

          <div>
            <label className="label" htmlFor="details">
              İzah
            </label>
            <textarea
              id="details"
              name="details"
              className="input min-h-28"
              placeholder="Orijinal mənbəyə keçid, hüquq sahibi barədə məlumat və s."
            />
          </div>

          <button type="submit" className="btn-primary w-full">
            Göndər
          </button>
          <p className="text-xs text-muted">
            Şikayət moderasiya komandasına göndərilir. Əsaslı hallarda model
            kataloqdan dərhal çıxarılır.
          </p>
        </form>
      )}
    </div>
  );
}
