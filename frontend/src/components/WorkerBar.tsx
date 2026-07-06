import { useEffect, useState } from "react";
import { api, WorkerInfo } from "../api";

const DOT: Record<string, string> = {
  ready: "bg-emerald-400",
  rendering: "bg-accent animate-pulse",
  downloading: "bg-amber-400",
  booting: "bg-amber-400",
  dead: "bg-neutral-600",
};

export function WorkerBar() {
  const [workers, setWorkers] = useState<WorkerInfo[]>([]);
  useEffect(() => {
    const load = () => api.workers().then(setWorkers).catch(() => {});
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  if (!workers.length)
    return <span className="text-xs text-neutral-500">no workers connected</span>;
  return (
    <div className="flex items-center gap-2">
      {workers.map((w) => (
        <span key={w.id} className="chip border-line bg-ink-850" title={`${w.gpu_name} · ${w.vram_gb}GB`}>
          <span className={`w-2 h-2 rounded-full ${DOT[w.boot_status] ?? "bg-neutral-600"}`} />
          {w.gpu_name || w.worker_key}
        </span>
      ))}
    </div>
  );
}
