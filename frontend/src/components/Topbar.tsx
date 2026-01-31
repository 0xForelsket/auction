import Link from "next/link";

export function Topbar() {
  return (
    <header className="flex flex-col gap-4 rounded-[28px] border border-ink/10 bg-surface/70 px-6 py-4 shadow-[0_12px_40px_-32px_rgba(15,23,42,0.6)] backdrop-blur md:flex-row md:items-center md:justify-between">
      <div className="flex flex-1 items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-ink text-surface shadow-soft md:hidden">
          <span className="font-display text-base">US</span>
        </div>
        <div className="relative flex-1">
          <input
            type="search"
            placeholder="Search records - English or Japanese"
            className="w-full rounded-2xl border border-ink/10 bg-canvas/80 px-4 py-3 text-sm text-ink shadow-inner outline-none transition focus:border-ink/30"
          />
          <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs text-ink/40">
            Ctrl+K
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Link
          href="/upload"
          className="rounded-2xl bg-ink px-4 py-2 text-sm font-semibold text-surface shadow-soft transition hover:-translate-y-0.5"
        >
          Upload
        </Link>
        <button className="flex items-center gap-2 rounded-2xl border border-ink/15 bg-canvas/80 px-4 py-2 text-sm text-ink/70 shadow-inner">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-mint text-ink">
            AO
          </span>
          Ops Lead
          <span className="text-ink/40">v</span>
        </button>
      </div>
    </header>
  );
}
