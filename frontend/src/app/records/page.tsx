import Link from "next/link";

const records = [
  {
    id: "rec-1",
    lot: "75241",
    venue: "Tokyo",
    model: "Porsche Taycan GTS",
    mileage: "8,000 km",
    score: "4.5",
    price: "JPY 91.15M",
    status: "Auto-pass",
  },
  {
    id: "rec-2",
    lot: "73547",
    venue: "Nagoya",
    model: "Toyota Harrier Z",
    mileage: "32,000 km",
    score: "4.0",
    price: "JPY 6.8M",
    status: "Auto-pass",
  },
  {
    id: "rec-3",
    lot: "25888",
    venue: "Osaka",
    model: "Nissan Note",
    mileage: "-",
    score: "-",
    price: "-",
    status: "Needs review",
  },
];

export default function RecordsPage() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Records</p>
          <h1 className="font-display text-3xl">Search USS sheets</h1>
        </div>
        <span className="rounded-full border border-ink/10 bg-canvas/80 px-4 py-2 text-xs uppercase tracking-[0.2em] text-ink/60">
          JP + EN search enabled
        </span>
      </header>

      <div className="rounded-[24px] border border-ink/10 bg-canvas/80 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs uppercase tracking-[0.2em] text-ink/45">Search</span>
          <input
            className="flex-1 rounded-2xl border border-ink/10 bg-surface/80 px-4 py-2 text-sm shadow-inner"
            placeholder="taycan OR porsche"
          />
          <button className="rounded-2xl border border-ink/10 bg-ink px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-surface">
            Filters
          </button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <aside className="h-fit rounded-[24px] border border-ink/10 bg-surface/80 p-5 shadow-soft">
          <h2 className="font-display text-lg">Quick Filters</h2>
          <div className="mt-5 space-y-6 text-sm">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/45">Venue</p>
              <div className="mt-3 space-y-2">
                {["Tokyo (JP)", "Nagoya (JP)", "Osaka (JP)"].map((venue) => (
                  <label key={venue} className="flex items-center justify-between rounded-xl border border-ink/10 bg-canvas/70 px-3 py-2">
                    <span>{venue}</span>
                    <input type="checkbox" className="accent-ink" defaultChecked />
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/45">Score</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {["5", "4.5", "4", "R"].map((score) => (
                  <button
                    key={score}
                    className="rounded-full border border-ink/10 bg-canvas/70 px-4 py-1 text-xs"
                  >
                    {score}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/45">Make</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {["Toyota", "Lexus", "Porsche", "BMW", "Mercedes", "Other"].map((make) => (
                  <button
                    key={make}
                    className="rounded-full border border-ink/10 bg-canvas/70 px-3 py-1 text-xs"
                  >
                    {make}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/45">Price Range</p>
              <div className="mt-3 flex gap-2">
                <input
                  placeholder="JPY ___00k"
                  className="w-24 rounded-xl border border-ink/10 bg-canvas/70 px-3 py-2 text-xs"
                />
                <span className="self-center text-xs text-ink/45">to</span>
                <input
                  placeholder="JPY ___00k"
                  className="w-24 rounded-xl border border-ink/10 bg-canvas/70 px-3 py-2 text-xs"
                />
              </div>
            </div>
          </div>
        </aside>

        <section className="rounded-[24px] border border-ink/10 bg-surface/80 p-6 shadow-soft">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl">Records</h2>
            <span className="text-xs uppercase tracking-[0.2em] text-ink/45">{records.length} results</span>
          </div>

          <div className="mt-5 overflow-hidden rounded-2xl border border-ink/10">
            <div className="grid grid-cols-[110px_130px_1.4fr_140px_80px_120px_120px] gap-4 bg-canvas/70 px-4 py-3 text-xs uppercase tracking-[0.2em] text-ink/45">
              <span>Lot</span>
              <span>Venue</span>
              <span>Model</span>
              <span>Mileage</span>
              <span>Score</span>
              <span>Price</span>
              <span>Status</span>
            </div>
            {records.map((record) => (
              <Link
                href={`/records/${record.id}`}
                key={record.id}
                className="grid grid-cols-[110px_130px_1.4fr_140px_80px_120px_120px] gap-4 border-t border-ink/10 px-4 py-3 text-sm transition hover:bg-canvas/60"
              >
                <span className="font-medium text-ink">{record.lot}</span>
                <span className="text-ink/60">{record.venue}</span>
                <span>{record.model}</span>
                <span>{record.mileage}</span>
                <span>{record.score}</span>
                <span>{record.price}</span>
                <span
                  className={`text-xs font-semibold uppercase tracking-[0.2em] ${
                    record.status === "Auto-pass" ? "text-mint" : "text-ember"
                  }`}
                >
                  {record.status}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
