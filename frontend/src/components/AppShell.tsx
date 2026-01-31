import { PropsWithChildren } from "react";
import { SideNav } from "@/components/SideNav";
import { Topbar } from "@/components/Topbar";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <div className="fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-[420px] w-[420px] rounded-full bg-accent/20 blur-3xl" />
        <div className="absolute right-[-120px] top-32 h-[360px] w-[360px] rounded-full bg-sun/30 blur-3xl" />
        <div className="absolute bottom-[-180px] left-[35%] h-[420px] w-[420px] rounded-full bg-mint/30 blur-[120px]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.7),_rgba(255,255,255,0))]" />
      </div>

      <div className="mx-auto flex w-full max-w-7xl gap-6 px-4 py-6 md:px-8">
        <SideNav />
        <div className="flex min-h-[calc(100vh-48px)] flex-1 flex-col gap-6">
          <Topbar />
          <main className="flex-1 rounded-[28px] border border-ink/10 bg-surface/80 p-6 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.55)] backdrop-blur">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
