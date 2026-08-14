import { NextResponse } from "next/server";

import { getCurrentUser } from "@/lib/auth";
import { hasEntitlement } from "@/lib/credits";
import { prisma } from "@/lib/prisma";
import { signDownloadToken } from "@/lib/download-token";

/**
 * Endirmənin 1-ci addımı: hüquq yoxlanışı.
 *
 * Sessiya + Entitlement yoxlanır, sonra 5 dəqiqəlik imzalı token verilir və
 * /api/file-a yönləndirilir. Bu ikimərhələli quruluş sonradan S3 presigned
 * URL-ə keçidi asanlaşdırır: /api/file əvəzinə birbaşa S3 linki qaytarılacaq.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ modelId: string }> },
) {
  const { modelId } = await params;

  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Giriş tələb olunur" }, { status: 401 });
  }

  const model = await prisma.model.findUnique({
    where: { id: modelId },
    select: {
      id: true,
      status: true,
      assets: {
        where: { kind: "SOURCE" },
        orderBy: { sortOrder: "asc" },
        take: 1,
        select: { id: true },
      },
    },
  });

  if (!model || model.status !== "PUBLISHED") {
    return NextResponse.json({ error: "Model tapılmadı" }, { status: 404 });
  }

  const asset = model.assets[0];
  if (!asset) {
    return NextResponse.json({ error: "Bu modelin faylı yüklənməyib" }, { status: 404 });
  }

  if (!(await hasEntitlement(user.id, model.id))) {
    return NextResponse.json(
      { error: "Bu modeli əvvəlcə əldə etməlisiniz" },
      { status: 403 },
    );
  }

  // Faktiki endirmə jurnalı — sui-istifadənin aşkarlanması üçün.
  await prisma.downloadLog.create({
    data: {
      userId: user.id,
      modelId: model.id,
      ip: request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null,
      userAgent: request.headers.get("user-agent"),
    },
  });

  const token = await signDownloadToken({
    userId: user.id,
    modelId: model.id,
    assetId: asset.id,
  });

  return NextResponse.redirect(new URL(`/api/file?token=${token}`, request.url));
}
