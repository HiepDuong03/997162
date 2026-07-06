import { useEffect, useRef, useState } from "react";
import { api, Character, SceneRef } from "../api";

export function LibraryPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [sceneRefs, setSceneRefs] = useState<SceneRef[]>([]);
  const [cName, setCName] = useState("");
  const [cLook, setCLook] = useState("");
  const [sName, setSName] = useState("");
  const [sEnv, setSEnv] = useState("");
  const fileRefs = useRef<Record<number, HTMLInputElement | null>>({});

  const load = () => {
    api.characters().then(setCharacters);
    api.sceneRefs().then(setSceneRefs);
  };
  useEffect(load, []);

  const addChar = async () => {
    if (!cName.trim()) return;
    await api.createCharacter({ name: cName.trim(), appearance: cLook.trim() });
    setCName(""); setCLook(""); load();
  };
  const addScene = async () => {
    if (!sName.trim()) return;
    await api.createSceneRef({ name: sName.trim(), environment: sEnv.trim() });
    setSName(""); setSEnv(""); load();
  };
  const upload = async (id: number, f?: File) => {
    if (f) { await api.uploadRef(id, f); load(); }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-8">
      {/* Characters */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-1">Characters</h2>
        <p className="text-sm text-neutral-500 mb-4">Reusable identities compiled into every shot.</p>
        <div className="card p-4 mb-4 space-y-3">
          <div>
            <label className="label">Name</label>
            <input className="input" value={cName} onChange={(e) => setCName(e.target.value)} placeholder="Elara" />
          </div>
          <div>
            <label className="label">Appearance</label>
            <input className="input" value={cLook} onChange={(e) => setCLook(e.target.value)}
              placeholder="young woman, short black hair, red coat, silver pendant" />
          </div>
          <button className="btn btn-primary" onClick={addChar}>Add character</button>
        </div>
        <div className="space-y-2">
          {characters.map((c) => (
            <div key={c.id} className="card p-3 flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-ink-800 overflow-hidden flex items-center justify-center shrink-0">
                {c.ref_image_path ? (
                  <img src={`/assets/${c.ref_image_path}`} className="w-full h-full object-cover" />
                ) : (
                  <span className="text-neutral-600 text-xs">no ref</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-white text-sm">{c.name}</div>
                <div className="text-xs text-neutral-500 truncate">{c.appearance}</div>
              </div>
              <input
                ref={(el) => (fileRefs.current[c.id] = el)}
                type="file" accept="image/*" className="hidden"
                onChange={(e) => upload(c.id, e.target.files?.[0])}
              />
              <button className="btn" onClick={() => fileRefs.current[c.id]?.click()}>
                {c.ref_image_path ? "Replace ref" : "Upload ref"}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Scene refs */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-1">Scenes</h2>
        <p className="text-sm text-neutral-500 mb-4">Environments, lighting and mood presets.</p>
        <div className="card p-4 mb-4 space-y-3">
          <div>
            <label className="label">Name</label>
            <input className="input" value={sName} onChange={(e) => setSName(e.target.value)} placeholder="Foggy forest" />
          </div>
          <div>
            <label className="label">Environment</label>
            <input className="input" value={sEnv} onChange={(e) => setSEnv(e.target.value)}
              placeholder="dense pine forest at dawn, mist between the trees" />
          </div>
          <button className="btn btn-primary" onClick={addScene}>Add scene</button>
        </div>
        <div className="space-y-2">
          {sceneRefs.map((s) => (
            <div key={s.id} className="card p-3">
              <div className="text-white text-sm">{s.name}</div>
              <div className="text-xs text-neutral-500 truncate">{s.environment}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
