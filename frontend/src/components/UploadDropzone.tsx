"use client";

export function UploadDropzone() {
  return (
    <div className="rounded-[28px] border border-dashed border-ink/30 bg-canvas/70 p-8 text-center">
      <p className="font-display text-xl text-ink">Drop USS screenshots here</p>
      <p className="mt-2 text-sm text-ink/60">
        JPEG or PNG - Up to 15MB - Auto-detect header table
      </p>
      <label className="mt-6 inline-flex cursor-pointer rounded-2xl bg-ink px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-surface shadow-soft">
        Select files
        <input type="file" multiple className="hidden" />
      </label>
    </div>
  );
}
