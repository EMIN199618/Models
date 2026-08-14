import Link from "next/link";
import { redirect } from "next/navigation";

import { UploadForm } from "@/components/UploadForm";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export const metadata = { title: "Yeni model" };

export default async function NewModelPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "ARTIST" && user.role !== "ADMIN") redirect("/models");

  const categories = await prisma.category.findMany({
    orderBy: { name: "asc" },
    select: { slug: true, name: true },
  });

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/studio" className="text-sm text-muted hover:text-foreground">
        ← Studiyaya qayıt
      </Link>
      <h1 className="mb-6 mt-2 text-2xl font-semibold">Yeni model yüklə</h1>
      <UploadForm categories={categories} />
    </div>
  );
}
