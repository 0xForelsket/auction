import Link from "next/link";

const headerData = [
  { label: "Date", value: "2024-10-17" },
  { label: "Venue", value: "Tokyo (1488th)" },
  { label: "Score", value: "4.5" },
  { label: "Mileage", value: "8,000 km" },
  { label: "Final", value: "JPY 91,150,000" },
  { label: "Model", value: "ZAA-J1NE" },
  { label: "Equipment", value: "AAC SR AW LEATHER PS PW DR" },
];

const sheetData = [
  { label: "Chassis", value: "WF0ZZZY1ZPSA" },
  { label: "Mileage", value: "7,496 km" },
  { label: "Notes", value: "Privacy glass / red calipers / dash cam" },
  { label: "Inspector", value: "Large cable" },
];

export default function RecordDetail({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Record detail</p>
          <h1 className="font-display text-3xl">Lot 75241 - Porsche Taycan GTS</h1>
          <p className="mt-2 text-sm text-ink/60">Document ID: {params.id}</p>
        </div>
        <div className="flex gap-3">
          <Link
            href="/review"
            className="rounded-2xl border border-ink/10 bg-canvas/80 px-4 py-2 text-xs uppercase tracking-[0.2em] text-ink/60"
          >
            Review queue
          </Link>
          <button className="rounded-2xl bg-ink px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-surface">
            Mark verified
          </button>
        </div>
      </header>

      <section className="grid gap-6 lg:grid-cols-2">
        <article className="rounded-[24px] border border-ink/10 bg-surface/85 p-6 shadow-soft">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl">From header</h2>
            <span className="rounded-full bg-mint/20 px-3 py-1 text-xs font-semibold text-ink">
              High confidence
            </span>
          </div>
          <div className="mt-6 space-y-4 text-sm">
            {headerData.map((item) => (
              <div key={item.label} className="flex items-start justify-between gap-4">
                <span className="text-ink/60">{item.label}</span>
                <span className="text-right font-medium text-ink">{item.value}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-[24px] border border-ink/10 bg-surface/85 p-6 shadow-soft">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl">From sheet</h2>
            <span className="rounded-full bg-sun/30 px-3 py-1 text-xs font-semibold text-ink">
              Medium confidence
            </span>
          </div>
          <div className="mt-6 space-y-4 text-sm">
            {sheetData.map((item) => (
              <div key={item.label} className="flex items-start justify-between gap-4">
                <span className="text-ink/60">{item.label}</span>
                <span className="text-right font-medium text-ink">{item.value}</span>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="rounded-[24px] border border-ink/10 bg-canvas/70 px-6 py-4 text-sm text-ember">
        * Mileage discrepancy: header shows 8 (x1000), sheet shows 7,496
      </section>
    </div>
  );
}
