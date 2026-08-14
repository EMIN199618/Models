"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import { createModelAction, type UploadState } from "@/actions/upload";
import { ARTIST_REVENUE_SHARE, MODEL_CREDIT_COST } from "@/lib/pricing";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="btn-primary" disabled={pending}>
      {pending ? "Yüklənir… (fayl böyükdürsə uzun çəkə bilər)" : "Moderasiyaya göndər"}
    </button>
  );
}

export function UploadForm({
  categories,
}: {
  categories: { slug: string; name: string }[];
}) {
  const [state, formAction] = useActionState<UploadState, FormData>(
    createModelAction,
    undefined,
  );

  return (
    <form action={formAction} className="space-y-6">
      <section className="card space-y-4 p-5">
        <h2 className="text-sm font-semibold text-muted">Əsas məlumat</h2>

        <div>
          <label className="label" htmlFor="title">
            Başlıq *
          </label>
          <input
            id="title"
            name="title"
            className="input"
            required
            placeholder="Minotti tipli künc divan"
          />
        </div>

        <div>
          <label className="label" htmlFor="description">
            Təsvir
          </label>
          <textarea
            id="description"
            name="description"
            className="input min-h-24"
            placeholder="Ölçülər, teksturaların həlli, hansı səhnədə istifadəyə uyğundur…"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="categorySlug">
              Kateqoriya
            </label>
            <select id="categorySlug" name="categorySlug" className="input">
              <option value="">Seçilməyib</option>
              {categories.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <span className="label">Qiymət</span>
            <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm">
              {MODEL_CREDIT_COST} Credit
              <span className="ml-2 text-xs text-muted">
                (vahid qiymət — bütün modellər üçün eynidir)
              </span>
            </p>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="tags">
            Teqlər (vergüllə)
          </label>
          <input
            id="tags"
            name="tags"
            className="input"
            placeholder="divan, yumşaq mebel, modern"
          />
        </div>
      </section>

      <section className="card space-y-4 p-5">
        <h2 className="text-sm font-semibold text-muted">Texniki parametrlər</h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="renderer">
              Render mühərriki *
            </label>
            <select id="renderer" name="renderer" className="input" defaultValue="CORONA">
              <option value="CORONA">Corona Renderer</option>
              <option value="VRAY">V-Ray</option>
              <option value="BOTH">Corona + V-Ray</option>
              <option value="OTHER">Digər</option>
            </select>
          </div>

          <div>
            <label className="label" htmlFor="formats">
              Formatlar (vergüllə)
            </label>
            <input id="formats" name="formats" className="input" placeholder="max, fbx, obj" />
          </div>

          <div>
            <label className="label" htmlFor="maxVersion">
              3ds Max versiyası
            </label>
            <input id="maxVersion" name="maxVersion" className="input" placeholder="2021" />
          </div>

          <div>
            <label className="label" htmlFor="polyCount">
              Poliqon sayı
            </label>
            <input
              id="polyCount"
              name="polyCount"
              type="number"
              min={0}
              className="input"
              placeholder="185000"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-5">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="hasTextures" className="accent-[var(--accent)]" />
            Teksturalar daxildir
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="isPbr" className="accent-[var(--accent)]" />
            PBR materiallar
          </label>
        </div>
      </section>

      <section className="card space-y-4 p-5">
        <h2 className="text-sm font-semibold text-muted">Fayllar</h2>

        <div>
          <label className="label" htmlFor="sourceFile">
            Mənbə faylı * <span className="font-normal">(satılan fayl — qorunur)</span>
          </label>
          <input
            id="sourceFile"
            name="sourceFile"
            type="file"
            className="input file:mr-3 file:rounded file:border-0 file:bg-surface file:px-3 file:py-1 file:text-foreground"
            accept=".zip,.rar,.7z,.max,.fbx,.obj,.blend"
            required
          />
          <p className="mt-1 text-xs text-muted">
            ZIP arxiv tövsiyə olunur (model + teksturalar). Maks. 500 MB.
          </p>
        </div>

        <div>
          <label className="label" htmlFor="previewGlb">
            3D önizləmə (.glb)
          </label>
          <input
            id="previewGlb"
            name="previewGlb"
            type="file"
            className="input file:mr-3 file:rounded file:border-0 file:bg-surface file:px-3 file:py-1 file:text-foreground"
            accept=".glb"
          />
          <p className="mt-1 text-xs text-muted">
            Brauzerdə fırladılan sadələşdirilmiş versiya. Əsl faylı buraya YÜKLƏMƏYİN —
            bu fayl hamıya açıqdır.
          </p>
        </div>

        <div>
          <label className="label" htmlFor="images">
            Render şəkilləri * (bir neçə seçə bilərsiniz)
          </label>
          <input
            id="images"
            name="images"
            type="file"
            multiple
            className="input file:mr-3 file:rounded file:border-0 file:bg-surface file:px-3 file:py-1 file:text-foreground"
            accept="image/jpeg,image/png,image/webp"
            required
          />
          <p className="mt-1 text-xs text-muted">Birinci şəkil kataloqda görünəcək.</p>
        </div>
      </section>

      {state?.error && (
        <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {state.error}
        </p>
      )}

      <div className="flex items-center gap-3">
        <SubmitButton />
        <p className="text-xs text-muted">
          Model admin təsdiqindən sonra kataloqda görünəcək. Hər endirmədən
          gəlirin {Math.round(ARTIST_REVENUE_SHARE * 100)}%-i sizə düşür.
        </p>
      </div>
    </form>
  );
}
