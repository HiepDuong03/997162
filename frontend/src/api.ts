export type ModelCaps = {
  model_id: string;
  display_name: string;
  supports_t2v: boolean;
  supports_i2v: boolean;
  supports_negative_prompt: boolean;
  supports_lora: boolean;
  steps: number;
  max_frames: number;
  default_resolution: string;
};

export type Character = {
  id: number;
  name: string;
  appearance: string;
  prompt_template: string;
  negative_prompt: string;
  ref_image_path: string | null;
  seed: number;
};

export type SceneRef = {
  id: number;
  name: string;
  environment: string;
  lighting: string;
  style: string;
  time_of_day: string;
  color_palette: string;
  atmosphere: string;
  negative_prompt: string;
};

export type Project = {
  id: number;
  name: string;
  description: string;
  model_id: string;
  width: number;
  height: number;
  fps: number;
};

export type Scene = {
  id: number;
  project_id: number;
  scene_ref_id: number | null;
  name: string;
  order: number;
  consistency_mode: "parallel" | "chained" | "lora";
};

export type Shot = {
  id: number;
  scene_id: number;
  order: number;
  character_ids: string;
  camera_preset: string;
  motion_preset: string;
  action_text: string;
  num_frames: number;
  clip_path: string | null;
};

export type Preset = { id: string; label: string; phrase: string };
export type WorkerInfo = {
  id: number;
  worker_key: string;
  gpu_name: string;
  vram_gb: number;
  boot_status: string;
};

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  models: () => fetch("/api/models").then(j<ModelCaps[]>),
  presets: () => fetch("/api/presets").then(j<{ camera: Preset[]; motion: Preset[] }>),
  workers: () => fetch("/api/worker/list").then(j<WorkerInfo[]>),

  projects: () => fetch("/api/projects").then(j<Project[]>),
  project: (id: number) => fetch(`/api/projects/${id}`).then(j<Project>),
  createProject: (body: Partial<Project>) =>
    fetch("/api/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<Project>),
  renderProject: (id: number) => fetch(`/api/projects/${id}/render`, { method: "POST" }).then(j),
  progress: (id: number) => fetch(`/api/projects/${id}/progress`).then(j<any>),

  scenes: (pid: number) => fetch(`/api/projects/${pid}/scenes`).then(j<Scene[]>),
  createScene: (body: Partial<Scene>) =>
    fetch("/api/scenes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<Scene>),
  updateScene: (id: number, body: Partial<Scene>) =>
    fetch(`/api/scenes/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<Scene>),
  renderScene: (id: number) => fetch(`/api/scenes/${id}/render`, { method: "POST" }).then(j),

  shots: (sid: number) => fetch(`/api/scenes/${sid}/shots`).then(j<Shot[]>),
  createShot: (body: Partial<Shot>) =>
    fetch("/api/shots", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<Shot>),
  updateShot: (id: number, body: Partial<Shot>) =>
    fetch(`/api/shots/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<Shot>),
  deleteShot: (id: number) => fetch(`/api/shots/${id}`, { method: "DELETE" }).then(j),
  previewPrompt: (id: number) => fetch(`/api/shots/${id}/preview-prompt`).then(j<{ prompt: string; negative: string }>),

  characters: () => fetch("/api/characters").then(j<Character[]>),
  createCharacter: (body: Partial<Character>) =>
    fetch("/api/characters", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<Character>),
  uploadRef: (id: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`/api/characters/${id}/ref-image`, { method: "POST", body: fd }).then(j<Character>);
  },
  sceneRefs: () => fetch("/api/scene-refs").then(j<SceneRef[]>),
  createSceneRef: (body: Partial<SceneRef>) =>
    fetch("/api/scene-refs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(j<SceneRef>),
};
