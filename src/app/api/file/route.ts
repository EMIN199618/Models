import { Readable } from "node:stream";
import { NextResponse } from "next/server";

import { prisma } from "@/lib/prisma";
import { verifyDownloadToken } from "@/lib/download-token";
import { objectExists, readObjectStream } from "@/lib/storage";

/**
 * Endirmənin 2-ci addımı: imzalı token ilə faylın verilməsi.
 *
 * Token 5 dəqiqəlik və (istifadəçi + model + asset) cütünə bağlıdır.
 * Yəni link paylaşılsa belə, tez bir zamanda etibarsız olur.
 */
export async function GET(request: Request) {
  const token = new URL(request.url).searchParams.get("token");
  if (!token) {
    return NextResponse.json({ error: "Token yoxdur" }, { status: 400 });
  }

  const payload = await verifyDownloadToken(token);
  if (!payload) {
    return NextResponse.json(
      { error: "Endirmə linki etibarsız və ya vaxtı keçib" },
      { status: 403 },
    );
  }

  const asset = await prisma.asset.findUnique({
    where: { id: payload.assetId },
    select: {
      storageKey: true,
      originalName: true,
      mimeType: true,
      sizeBytes: true,
      modelId: true,
      kind: true,
    },
  });

  // Token başqa modelin faylına işarə edirsə, rədd edilir.
  if (!asset || asset.modelId !== payload.modelId || asset.kind !== "SOURCE") {
    return NextResponse.json({ error: "Fayl tapılmadı" }, { status: 404 });
  }

  if (!(await objectExists(asset.storageKey))) {
    return NextResponse.json({ error: "Fayl storage-da yoxdur" }, { status: 404 });
  }

  const nodeStream = readObjectStream(asset.storageKey);
  const webStream = Readable.toWeb(nodeStream as Readable) as ReadableStream<Uint8Array>;

  return new NextResponse(webStream, {
    headers: {
      "Content-Type": asset.mimeType,
      "Content-Length": asset.sizeBytes.toString(),
      "Content-Disposition": `attachment; filename="${encodeURIComponent(asset.originalName)}"`,
      "Cache-Control": "private, no-store",
    },
  });
}
