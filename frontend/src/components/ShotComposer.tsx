import { useEffect, useMemo, useState } from "react";
import { api, Character, ModelCaps, Preset, Scene, Shot } from "../api";

export function ShotComposer({
  scene,
  shot,
  characters,
  camera,
  motion,
  model,
  onSaved,
  onClose,
}: {
  scene: Scene;
  shot: Shot | null;
  characters: Character[];
  camera: Preset[];
  motion: Preset[];
  model?: ModelCaps;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [action, setAction] = useState(shot?.action_text ?? "");
  const [charIds, setCharIds] = useState<number[]>(
    shot?.character_ids ? shot.character_ids.split(",").filter(Boolean).map(Number) : []
  );
  const [cam, setCam] = useState(shot?.camera_preset ?? "slow_push_in");
  const [mot, setMot] = useState(shot?.motion_preset ?? "walking");
  const [preview, setPreview] = useState<{ prompt: string; negative: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const toggleChar = (id: number) =>
    setCharIds((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  // Live prompt preview: save a draft then ask backend to compile.
  const body = useMemo(
    () => ({
      scene_id: scene.id,
      action_text: action,
      camera_preset: cam,
      motion_preset: mot,
      character_ids: charIds.join(","),
    }),
    [scene.id, action, cam, mot, charIds]
  );

  useEffect(() => {
    const t = setTimeout(async () => {
      try {
        // persist first (draft), then compile from server for a single source of truth
        const saved = shot
          ? await api.updateShot(shot.id, body)
          : null;
        const id = saved?.id ?? shot?.id;
        if (id) setPreview(await api.previewPrompt(id));
      } catch {
        /* ignore while typing */
      }
    }, 400);
    return () => clearTimeout(t);
  }, [body, shot]);

  const save = async () => {
    setSaving(true);
    try {
      if (shot) await api.updateShot(shot.id, body);
      else await api.createShot(body);
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-30 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-2xl p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white">{shot ? "Edit shot" : "New shot"}</h3>
          <button className="btn" onClick={onClose}>Close</button>
        </div>

        <label className="label">Action (just describe what happens)</label>
        <input
          className="input mb-4"
          autoFocus
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="walks into the clearing and looks up"
        />

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Camera</label>
            <select className="input" value={cam} onChange={(e) => setCam(e.target.value)}>
              {camera.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Motion</label>
            <select className="input" value={mot} onChange={(e) => setMot(e.target.value)}>
              {motion.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>
        </div>

        <label className="label">Characters</label>
        <div className="flex flex-wrap gap-2 mb-4">
          {characters.map((c) => (
            <button
              key={c.id}
              onClick={() => toggleChar(c.id)}
              className={`chip ${
                charIds.includes(c.id) ? "border-accent bg-accent/20 text-white" : "border-line bg-ink-850"
              }`}
            >
              {c.name}
            </button>
          ))}
          {!characters.length && (
            <span className="text-xs text-neutral-500">No characters yet — add them in Library.</span>
          )}
        </div>

        <label className="label">Compiled prompt {model && `· ${model.display_name}`}</label>
        <div className="card bg-ink-850 p-3 text-xs text-neutral-400 min-h-[64px] mb-4 whitespace-pre-wrap">
          {preview?.prompt || <span className="text-neutral-600">Type an action to see the compiled prompt…</span>}
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={saving || !action.trim()}>
            {shot ? "Save" : "Add shot"}
          </button>
        </div>
      </div>
    </div>
  );
}
