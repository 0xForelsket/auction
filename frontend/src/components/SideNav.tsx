"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/records", label: "Records" },
  { href: "/review", label: "Review" },
  { href: "/upload", label: "Uploads" },
  { href: "/exports", label: "Exports" },
];

export function SideNav() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-56 flex-shrink-0 flex-col gap-6 rounded-[28px] border border-ink/10 bg-surface/70 p-6 shadow-[0_12px_40px_-32px_rgba(15,23,42,0.6)] backdrop-blur md:flex">
      <div className="flex items-center gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-2xl bg-ink text-surface shadow-soft">
          <span className="font-display text-lg">US</span>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-ink/50">Auction OCR</p>
          <p className="font-display text-lg">Ops Workspace</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-2 text-sm">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between rounded-2xl px-4 py-3 transition-all ${
                isActive
                  ? "bg-ink text-surface shadow-soft"
                  : "text-ink/70 hover:bg-ink/5"
              }`}
            >
              <span className="font-medium tracking-wide">{item.label}</span>
              <span
                className={`h-2 w-2 rounded-full ${
                  isActive ? "bg-sun" : "bg-transparent group-hover:bg-sun/60"
                }`}
              />
            </Link>
          );
        })}
      </nav>

      <div className="rounded-2xl border border-ink/10 bg-canvas/70 p-4 text-xs text-ink/60">
        <p className="font-semibold uppercase tracking-[0.2em] text-ink/50">Quick status</p>
        <div className="mt-3 flex items-center justify-between">
          <span>Auto-pass rate</span>
          <span className="font-display text-base text-ink">82%</span>
        </div>
        <div className="mt-2 flex items-center justify-between">
          <span>In queue</span>
          <span className="font-display text-base text-ink">3</span>
        </div>
      </div>
    </aside>
  );
}
