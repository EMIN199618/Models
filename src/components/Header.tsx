import Link from "next/link";

import { logoutAction } from "@/actions/auth";
import type { SessionUser } from "@/lib/auth";

export function Header({ user }: { user: SessionUser | null }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center gap-6 px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Arx<span className="text-accent">via</span>
        </Link>

        <nav className="hidden items-center gap-4 text-sm text-muted sm:flex">
          <Link href="/models" className="hover:text-foreground">
            Kataloq
          </Link>
          <Link href="/pricing" className="hover:text-foreground">
            Qiymətlər
          </Link>
          {user ? (
            <Link href="/favorites" className="hover:text-foreground">
              Seçilmişlər
            </Link>
          ) : null}
          {user?.role === "ARTIST" || user?.role === "ADMIN" ? (
            <Link href="/studio" className="hover:text-foreground">
              Studiya
            </Link>
          ) : null}
          {user?.role === "ADMIN" ? (
            <Link href="/admin" className="hover:text-foreground">
              Admin
            </Link>
          ) : null}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {user ? (
            <>
              <span
                className="badge border-accent/40 text-accent"
                title="Credit balansınız"
              >
                {user.creditBalance} Credit
              </span>
              <Link
                href="/account"
                className="hidden text-sm text-muted hover:text-foreground sm:block"
              >
                {user.name}
              </Link>
              <form action={logoutAction}>
                <button type="submit" className="btn-ghost px-3 py-1.5 text-xs">
                  Çıxış
                </button>
              </form>
            </>
          ) : (
            <>
              <Link href="/login" className="btn-ghost px-3 py-1.5 text-xs">
                Giriş
              </Link>
              <Link href="/register" className="btn-primary px-3 py-1.5 text-xs">
                Qeydiyyat
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
