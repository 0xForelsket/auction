import { UploadDropzone } from "@/components/UploadDropzone";

const recentUploads = [
  { name: "USS_Tokyo_75241.jpg", status: "Processing" },
  { name: "USS_Nagoya_73547.jpg", status: "Done" },
  { name: "USS_Osaka_25888.jpg", status: "Review" },
];

export default function UploadPage() {
  return (
    <div className="flex flex-col gap-8">
      <header>
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Uploads</p>
        <h1 className="font-display text-3xl">Send new auction sheets</h1>
        <p className="mt-2 text-sm text-ink/60">
          The system prioritizes the blue header table for high-confidence extraction.
        </p>
      </header>

      <UploadDropzone />

      <section className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="rounded-[24px] border border-ink/10 bg-surface/85 p-6 shadow-soft">
          <h2 className="font-display text-xl">What happens next</h2>
          <ol className="mt-4 space-y-3 text-sm text-ink/70">
            <li>1. Preprocess image (denoise + upscale).</li>
            <li>2. Extract header table fields (lot, venue, score, price).</li>
            <li>3. Scan sheet for chassis, notes, and mileage checks.</li>
            <li>4. Auto-pass if P0 fields validate.</li>
          </ol>
        </div>

        <aside className="rounded-[24px] border border-ink/10 bg-canvas/70 p-6 shadow-soft">
          <h2 className="font-display text-lg">Recent uploads</h2>
          <div className="mt-4 space-y-3 text-sm">
            {recentUploads.map((upload) => (
              <div
                key={upload.name}
                className="flex items-center justify-between rounded-2xl border border-ink/10 bg-surface/80 px-3 py-2"
              >
                <span className="text-ink/70">{upload.name}</span>
                <span
                  className={`text-xs font-semibold uppercase tracking-[0.2em] ${
                    upload.status === "Done"
                      ? "text-mint"
                      : upload.status === "Review"
                      ? "text-ember"
                      : "text-ink/50"
                  }`}
                >
                  {upload.status}
                </span>
              </div>
            ))}
          </div>
        </aside>
      </section>
    </div>
  );
}
