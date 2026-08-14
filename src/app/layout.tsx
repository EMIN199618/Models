import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { Header } from "@/components/Header";
import { getCurrentUser } from "@/lib/auth";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "Arxvia — 3D model marketplace",
    template: "%s · Arxvia",
  },
  description:
    "3ds Max, Corona Renderer və V-Ray üçün peşəkar 3D modellər. Axtar, önizlə, endir.",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const user = await getCurrentUser();

  return (
    <html lang="az">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Header user={user} />
        <main className="mx-auto min-h-[calc(100vh-8rem)] w-full max-w-7xl px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-border py-6 text-center text-xs text-muted">
          Arxvia — MVP · Bütün modellər müəllif hüququ qaydalarına tabedir
        </footer>
      </body>
    </html>
  );
}
