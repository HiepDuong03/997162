import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Character, ModelCaps, Preset, Project, Scene, Shot } from "../api";
import { ShotComposer } from "../components/ShotComposer";

type Progress = {
  total_jobs: number;
  done: number;
  pct: number;
  counts: Record<string, number>;
  shots: { id: number; clip_path: string | null }[];
};

export function ProjectPage() {
  const { id } = useParams();
  const pid = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [shotsByScene, setShotsByScene] = useState<Record<number, Shot[]>>({});
  const [characters, setCharacters] = useState<Character[]>([]);
  const [camera, setCamera] = useState<Preset[]>([]);
  const [motion, setMotion] = useState<Preset[]>([]);
  const [models, setModels] = useState<ModelCaps[]>([]);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [composer, setComposer] = useState<{ scene: Scene; shot: Shot } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const loadShots = useCallback(async (scs: Scene[]) => {
    const map: Record<number, Shot[]> = {};
    await Promise.all(scs.map(async (s) => (map[s.id] = await api.shots(s.id))));
    setShotsByScene(map);
  }, []);

  const loadAll = useCallback(async () => {
    const [p, scs] = await Promise.all([api.project(pid), api.scenes(pid)]);
    setProject(p);
    setScenes(scs);
    await loadShots(scs);
  }, [pid, loadShots]);

  useEffect(() => {
    loadAll();
    api.characters().then(setCharacters);
    api.presets().then((p) => {
      setCamera(p.camera);
      setMotion(p.motion);
    });
    api.models().then(setModels);
  }, [loadAll]);

  // Live progress over WebSocket.
  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/projects/${pid}`);
    ws.onmessage = (e) => setProgress(JSON.parse(e.data));
    wsRef.current = ws;
    return () => ws.close();
  }, [pid]);

  const model = models.find((m) => m.model_id === project?.model_id);

  const addScene = async () => {
    const sc = await api.createScene({
      project_id: pid,
      name: `Scene ${scenes.length + 1}`,
      order: scenes.length,
    });
    await loadAll();
    return sc;
  };

  const addShot = async (scene: Scene) => {
    const shot = await api.createShot({
      scene_id: scene.id,
      order: (shotsByScene[scene.id]?.length ?? 0),
      action_text: "",
      camera_preset: "slow_push_in",
      motion_preset: "walking",
    });
    setComposer({ scene, shot });
  };

  const setMode = async (scene: Scene, mode: Scene["consistency_mode"]) => {
    await api.updateScene(scene.id, { consistency_mode: mode });
    loadAll();
  };

  const renderAll = async () => {
    await api.renderProject(pid);
  };

  const [exporting, setExporting] = useState(false);
  const [exportUrl, setExportUrl] = useState<string | null>(null);
  const exportProject = async () => {
    setExporting(true);
    setExportUrl(null);
    try {
      const res = await fetch(`/api/projects/${pid}/export`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setExportUrl(data.url);
    } catch (e) {
      alert("Export failed: " + (e as Error).message);
    } finally {
      setExporting(false);
    }
  };

  const clipFor = (shotId: number) => progress?.shots.find((s) => s.id === shotId)?.clip_path;

  if (!project) return <div className="text-neutral-500">Loading…</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">{project.name}</h1>
          <p className="text-sm text-neutral-500">
            {project.width}×{project.height} · {project.fps}fps · {project.model_id}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={addScene}>+ Scene</button>
          <button className="btn" onClick={exportProject} disabled={exporting}>
            {exporting ? "Exporting…" : "Export mp4"}
          </button>
          <button className="btn btn-primary" onClick={renderAll}>Render all</button>
        </div>
      </div>

      {exportUrl && (
        <div className="card p-4 mb-6 flex items-center justify-between">
          <span className="text-sm text-emerald-400">Export ready.</span>
          <a className="btn btn-primary" href={exportUrl} target="_blank" rel="noreferrer">
            Open / download
          </a>
        </div>
      )}

      {progress && progress.total_jobs > 0 && (
        <div className="card p-4 mb-6">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-neutral-400">
              {progress.done}/{progress.total_jobs} shots rendered
            </span>
            <span className="text-neutral-500">
              {Object.entries(progress.counts)
                .map(([k, v]) => `${v} ${k}`)
                .join(" · ")}
            </span>
          </div>
          <div className="h-2 rounded-full bg-ink-800 overflow-hidden">
            <div className="h-full bg-accent transition-all" style={{ width: `${progress.pct}%` }} />
          </div>
        </div>
      )}

      <div className="space-y-6">
        {scenes.map((scene) => (
          <div key={scene.id} className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <span className="font-medium text-white">{scene.name}</span>
                <select
                  className="input !w-auto !py-1 text-xs"
                  value={scene.consistency_mode}
                  onChange={(e) => setMode(scene, e.target.value as Scene["consistency_mode"])}
                  title="parallel = fast; chained = strong character identity"
                >
                  <option value="parallel">parallel (fast)</option>
                  <option value="chained">chained (identity)</option>
                </select>
              </div>
              <div className="flex gap-2">
                <button className="btn" onClick={() => addShot(scene)}>+ Shot</button>
                <button className="btn" onClick={() => api.renderScene(scene.id)}>Render scene</button>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {(shotsByScene[scene.id] ?? []).map((shot) => {
                const clip = clipFor(shot.id) ?? shot.clip_path;
                return (
                  <div
                    key={shot.id}
                    className="card bg-ink-850 overflow-hidden cursor-pointer hover:border-accent"
                    onClick={() => setComposer({ scene, shot })}
                  >
                    <div className="aspect-video bg-ink-800 flex items-center justify-center">
                      {clip ? (
                        <video src={`/assets/${clip}`} className="w-full h-full object-cover" muted loop
                          onMouseEnter={(e) => e.currentTarget.play()}
                          onMouseLeave={(e) => e.currentTarget.pause()} />
                      ) : (
                        <span className="chip border-line bg-ink-900 text-neutral-500">queued</span>
                      )}
                    </div>
                    <div className="p-2 text-xs text-neutral-400 truncate">
                      {shot.action_text || <span className="text-neutral-600">empty shot</span>}
                    </div>
                  </div>
                );
              })}
              {!(shotsByScene[scene.id]?.length) && (
                <div className="text-xs text-neutral-600 col-span-full py-6 text-center">
                  No shots. Add one to start.
                </div>
              )}
            </div>
          </div>
        ))}
        {!scenes.length && (
          <div className="text-sm text-neutral-500 py-12 text-center border border-dashed border-line rounded-xl">
            No scenes yet. Add a scene, then shots.
          </div>
        )}
      </div>

      {composer && (
        <ShotComposer
          scene={composer.scene}
          shot={composer.shot}
          characters={characters}
          camera={camera}
          motion={motion}
          model={model}
          onSaved={loadAll}
          onClose={() => setComposer(null)}
        />
      )}
    </div>
  );
}
