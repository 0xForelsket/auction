import Link from "next/link";

const stats = [
  { label: "Processed Today", value: "12", helper: "+4 vs yesterday" },
  { label: "In Review", value: "3", helper: "2 require mileage check" },
  { label: "Failed", value: "1", helper: "OCR timeouts" },
  { label: "Avg Time", value: "8.2s", helper: "header-first pipeline" },
];

const recentRecords = [
  {
    time: "10:30",
    lot: "75241",
    model: "Porsche Taycan",
    mileage: "8,000 km",
    score: "4.5",
    price: "JPY 91.15M",
    status: "Approved",
  },
  {
    time: "10:28",
    lot: "73547",
    model: "Toyota Harrier",
    mileage: "32,000 km",
    score: "4.0",
    price: "JPY 6.8M",
    status: "Approved",
  },
  {
    time: "10:25",
    lot: "25888",
    model: "Nissan Note",
    mileage: "-",
    score: "-",
    price: "-",
    status: "Review",
  },
];

export default function Dashboard() {
  return (
    <div className="flex h-full flex-col gap-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Dashboard</p>
          <h1 className="font-display text-3xl text-ink">Today at a glance</h1>
        </div>
        <div className="rounded-2xl border border-ink/10 bg-canvas/80 px-4 py-3 text-sm text-ink/60 shadow-inner">
          Last sync: 10:42 AM - USS Tokyo
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat, index) => (
          <article
            key={stat.label}
            className="animate-rise rounded-[24px] border border-ink/10 bg-surface/90 p-5 shadow-soft"
            style={{ animationDelay: `${index * 120}ms` }}
          >
            <p className="text-xs uppercase tracking-[0.2em] text-ink/45">{stat.label}</p>
            <div className="mt-4 flex items-end justify-between">
              <span className="font-display text-3xl text-ink">{stat.value}</span>
              <span className="text-xs text-ink/50">{stat.helper}</span>
            </div>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-[28px] border border-ink/10 bg-surface/80 p-6 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/45">Quick actions</p>
              <h2 className="font-display text-2xl">Move faster</h2>
            </div>
            <span className="rounded-full bg-mint/20 px-3 py-1 text-xs text-ink/60">
              SLA 24h
            </span>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {[
              { href: "/upload", title: "Upload", desc: "Drop new USS sheets" },
              { href: "/review", title: "Review Queue", desc: "Resolve exceptions" },
              { href: "/exports", title: "Export", desc: "Ship CSV to buyers" },
            ].map((item) => (
              <Link
                key={item.title}
                href={item.href}
                className="group rounded-2xl border border-ink/10 bg-canvas/80 p-4 text-left shadow-inner transition hover:-translate-y-1"
              >
                <p className="text-xs uppercase tracking-[0.2em] text-ink/45">{item.title}</p>
                <p className="mt-3 font-display text-lg text-ink">{item.desc}</p>
                <span className="mt-4 inline-flex items-center text-xs text-ink/50">
                  Open &gt;
                </span>
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-[28px] border border-ink/10 bg-surface/80 p-6 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/45">Processing health</p>
              <h2 className="font-display text-2xl">Auto-pass trending up</h2>
            </div>
          </div>
          <div className="mt-6 space-y-4 text-sm">
            <div className="flex items-center justify-between rounded-2xl border border-ink/10 bg-canvas/70 px-4 py-3">
              <span className="text-ink/70">Header extraction</span>
              <span className="font-display text-lg text-ink">93%</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-ink/10 bg-canvas/70 px-4 py-3">
              <span className="text-ink/70">Sheet OCR (supplemental)</span>
              <span className="font-display text-lg text-ink">74%</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-ink/10 bg-canvas/70 px-4 py-3">
              <span className="text-ink/70">Needs review</span>
              <span className="font-display text-lg text-ember">18%</span>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-[28px] border border-ink/10 bg-surface/80 p-6 shadow-soft">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-ink/45">Recent records</p>
            <h2 className="font-display text-2xl">Latest uploads</h2>
          </div>
          <Link href="/records" className="text-sm text-ink/60 hover:text-ink">
            View all &gt;
          </Link>
        </div>
        <div className="mt-6 overflow-hidden rounded-2xl border border-ink/10">
          <div className="grid grid-cols-[90px_90px_1.4fr_1fr_80px_120px_120px] gap-4 bg-canvas/70 px-4 py-3 text-xs uppercase tracking-[0.2em] text-ink/45">
            <span>Time</span>
            <span>Lot</span>
            <span>Model</span>
            <span>Mileage</span>
            <span>Score</span>
            <span>Price</span>
            <span>Status</span>
          </div>
          {recentRecords.map((record) => (
            <div
              key={record.lot}
              className="grid grid-cols-[90px_90px_1.4fr_1fr_80px_120px_120px] gap-4 border-t border-ink/10 px-4 py-3 text-sm"
            >
              <span className="text-ink/60">{record.time}</span>
              <span className="font-medium text-ink">{record.lot}</span>
              <span>{record.model}</span>
              <span>{record.mileage}</span>
              <span>{record.score}</span>
              <span>{record.price}</span>
              <span
                className={`text-xs font-semibold uppercase tracking-[0.2em] ${
                  record.status === "Approved" ? "text-mint" : "text-ember"
                }`}
              >
                {record.status}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
