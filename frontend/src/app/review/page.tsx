import Link from "next/link";

const reviewItems = [
  {
    id: "25888",
    model: "Nissan Note",
    date: "Oct 18, 2024",
    issue: "Missing: score",
  },
  {
    id: "34521",
    model: "Mazda CX-5",
    date: "Oct 17, 2024",
    issue: "Mileage discrepancy",
    detail: "Header: 15k, Sheet: 14,235",
  },
  {
    id: "12207",
    model: "Mercedes CLA250",
    date: "Oct 17, 2024",
    issue: "Unclear chassis number",
  },
];

export default function ReviewPage() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Review queue</p>
          <h1 className="font-display text-3xl">3 items pending</h1>
        </div>
        <span className="rounded-full bg-ember/15 px-4 py-2 text-xs uppercase tracking-[0.2em] text-ember">
          Exceptions only
        </span>
      </header>

      <section className="rounded-[28px] border border-ink/10 bg-surface/85 p-6 shadow-soft">
        <div className="space-y-4">
          {reviewItems.map((item) => (
            <div key={item.id} className="rounded-2xl border border-ink/10 bg-canvas/70 p-4">
              <div className="flex flex-wrap items-center gap-4">
                <div className="h-16 w-20 rounded-xl bg-[linear-gradient(135deg,_rgba(29,26,22,0.1),_rgba(255,255,255,0.8))]" />
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <span className="font-display text-lg text-ink">{item.id}</span>
                    <span className="text-sm text-ink/60">{item.model}</span>
                  </div>
                  <p className="text-xs uppercase tracking-[0.2em] text-ink/45">{item.date}</p>
                </div>
                <span className="rounded-full bg-ember/15 px-3 py-1 text-xs font-semibold text-ember">
                  {item.issue}
                </span>
                <Link
                  href={`/records/${item.id}`}
                  className="rounded-2xl border border-ink/10 bg-ink px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-surface"
                >
                  Review &gt;
                </Link>
              </div>
              {item.detail && (
                <p className="mt-3 text-xs text-ink/60">{item.detail}</p>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-2xl border border-ink/10 bg-canvas/70 px-4 py-3 text-xs text-ink/60">
          Keyboard: [Tab] Next field - [Enter] Save & Next - [Esc] Skip
        </div>
      </section>
    </div>
  );
}
