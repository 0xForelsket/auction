export default function ExportsPage() {
  return (
    <div className="flex flex-col gap-8">
      <header>
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Exports</p>
        <h1 className="font-display text-3xl">Send data downstream</h1>
        <p className="mt-2 text-sm text-ink/60">
          Download filtered CSVs or push to buyers once records are verified.
        </p>
      </header>

      <section className="grid gap-6 lg:grid-cols-3">
        {[
          { title: "All verified", desc: "Export only verified records", action: "Download CSV" },
          { title: "Today's auction", desc: "Tokyo, Nagoya, Osaka", action: "Download CSV" },
          { title: "Needs review", desc: "Share exception list", action: "Download CSV" },
        ].map((card) => (
          <div
            key={card.title}
            className="rounded-[24px] border border-ink/10 bg-surface/85 p-6 shadow-soft"
          >
            <p className="text-xs uppercase tracking-[0.2em] text-ink/45">{card.title}</p>
            <p className="mt-3 text-sm text-ink/70">{card.desc}</p>
            <button className="mt-6 rounded-2xl bg-ink px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-surface">
              {card.action}
            </button>
          </div>
        ))}
      </section>

      <section className="rounded-[24px] border border-ink/10 bg-canvas/70 p-6 shadow-soft">
        <h2 className="font-display text-xl">Recent exports</h2>
        <div className="mt-4 space-y-3 text-sm">
          {[
            { name: "verified-2024-10-18.csv", time: "2 min ago" },
            { name: "tokyo-2024-10-18.csv", time: "30 min ago" },
            { name: "review-queue.csv", time: "1 hour ago" },
          ].map((item) => (
            <div
              key={item.name}
              className="flex items-center justify-between rounded-2xl border border-ink/10 bg-surface/80 px-4 py-3"
            >
              <span>{item.name}</span>
              <span className="text-xs text-ink/50">{item.time}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
