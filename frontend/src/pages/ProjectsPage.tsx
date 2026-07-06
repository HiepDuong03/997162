import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ModelCaps, Project } from "../api";

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [models, setModels] = useState<ModelCaps[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const load = () => api.projects().then(setProjects).catch(() => {});
  useEffect(() => {
    load();
    api.models().then(setModels).catch(() => {});
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    await api.createProject({ name: name.trim(), model_id: models[0]?.model_id });
    setName("");
    setCreating(false);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Projects</h1>
          <p className="text-sm text-neutral-500">Compose scenes and shots, render in parallel.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>
          + New project
        </button>
      </div>

      {creating && (
        <div className="card p-4 mb-6 flex gap-3 items-end">
          <div className="flex-1">
            <label className="label">Project name</label>
            <input
              className="input"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && create()}
              placeholder="My first film"
            />
          </div>
          <button className="btn btn-primary" onClick={create}>Create</button>
          <button className="btn" onClick={() => setCreating(false)}>Cancel</button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}`} className="card p-5 hover:border-accent transition-colors">
            <div className="font-medium text-white">{p.name}</div>
            <div className="text-xs text-neutral-500 mt-2">
              {p.width}×{p.height} · {p.fps}fps · {p.model_id}
            </div>
          </Link>
        ))}
        {!projects.length && !creating && (
          <div className="text-sm text-neutral-500 col-span-full py-12 text-center border border-dashed border-line rounded-xl">
            No projects yet. Create one to get started.
          </div>
        )}
      </div>
    </div>
  );
}
