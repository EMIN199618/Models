import "server-only";

import { SignJWT, jwtVerify } from "jose";

/**
 * Qısamüddətli imzalı endirmə tokeni.
 *
 * Niyə lazımdır: endirmə linki paylaşıla bilər. Token 5 dəqiqədən sonra
 * etibarsız olur və konkret (istifadəçi + model) cütünə bağlıdır — yəni
 * başqası linki tapsa belə, faylı ala bilmir.
 */

const TTL_SECONDS = 300; // 5 dəqiqə

function secret(): Uint8Array {
  const raw = process.env.DOWNLOAD_SECRET;
  if (!raw || raw.length < 32) {
    throw new Error("DOWNLOAD_SECRET təyin olunmayıb və ya 32 simvoldan qısadır");
  }
  return new TextEncoder().encode(raw);
}

export async function signDownloadToken(params: {
  userId: string;
  modelId: string;
  assetId: string;
}): Promise<string> {
  return new SignJWT({ uid: params.userId, mid: params.modelId, aid: params.assetId })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${TTL_SECONDS}s`)
    .sign(secret());
}

export async function verifyDownloadToken(
  token: string,
): Promise<{ userId: string; modelId: string; assetId: string } | null> {
  try {
    const { payload } = await jwtVerify(token, secret(), { algorithms: ["HS256"] });
    if (
      typeof payload.uid !== "string" ||
      typeof payload.mid !== "string" ||
      typeof payload.aid !== "string"
    ) {
      return null;
    }
    return { userId: payload.uid, modelId: payload.mid, assetId: payload.aid };
  } catch {
    return null;
  }
}
