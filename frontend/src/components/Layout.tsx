import { Link, Outlet, useLocation } from "react-router-dom";
import { WorkerBar } from "./WorkerBar";

export function Layout() {
  const loc = useLocation();
  const nav = [
    { to: "/", label: "Projects" },
    { to: "/library", label: "Library" },
  ];
  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-line bg-ink-900/80 backdrop-blur sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-6">
          <Link to="/" className="font-semibold tracking-tight text-white flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-accent" />
            OpenFlow
          </Link>
          <nav className="flex gap-1">
            {nav.map((n) => {
              const active = n.to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(n.to);
              return (
                <Link
                  key={n.to}
                  to={n.to}
                  className={`px-3 py-1.5 rounded-lg text-sm ${
                    active ? "bg-ink-800 text-white" : "text-neutral-400 hover:text-white"
                  }`}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto">
            <WorkerBar />
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
