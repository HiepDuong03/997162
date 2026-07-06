#!/usr/bin/env bash
# OpenFlow Kaggle worker bootstrap.
#
# Models load from ONE of:
#   (a) an attached Kaggle Dataset at /kaggle/input/openflow-wan22/  (if you made one), or
#   (b) downloaded fresh to /kaggle/temp/models via download_models.py  (default).
# We use /kaggle/temp (~50GB) NOT /kaggle/working (~20GB) — the 4 UNet GGUFs won't
# fit in working. Run in a GPU notebook cell with `!bash kaggle_bootstrap.sh`.
set -e

WORK=/kaggle/working
COMFY=$WORK/ComfyUI
DATASET_SRC=/kaggle/input/openflow-wan22
TEMP_MODELS=/kaggle/temp/models
export QUANT="${QUANT:-Q4_K_M}"     # Q3_K_M to save disk; Q5_K_M for best quality

echo "== RAM check (Kaggle ~13GB; GGUF load spikes it) =="
python - <<'PY'
import psutil; print(f"RAM available: {psutil.virtual_memory().available/1e9:.1f} GB")
PY

echo "== install ComfyUI =="
if [ ! -d "$COMFY" ]; then
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "$COMFY"
fi
pip -q install -r "$COMFY/requirements.txt"

echo "== custom nodes: ComfyUI-GGUF (city96) + VideoHelperSuite =="
cd "$COMFY/custom_nodes"
[ -d ComfyUI-GGUF ] || git clone --depth 1 https://github.com/city96/ComfyUI-GGUF
pip -q install "gguf>=0.13.0" || pip -q install gguf==0.13.0
pip -q install -r ComfyUI-GGUF/requirements.txt || true
[ -d ComfyUI-VideoHelperSuite ] || git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
pip -q install -r ComfyUI-VideoHelperSuite/requirements.txt || true
pip -q install requests psutil huggingface_hub

# ---- pick model source ----
if [ -d "$DATASET_SRC" ]; then
  MODELS_SRC="$DATASET_SRC"
  echo "== using attached Kaggle Dataset: $MODELS_SRC =="
else
  MODELS_SRC="$TEMP_MODELS"
  echo "== no dataset attached -> downloading models to $TEMP_MODELS (QUANT=$QUANT) =="
  cd "$WORK/openflow/worker" 2>/dev/null || cd /kaggle/working
  MODELS_DIR="$TEMP_MODELS" QUANT="$QUANT" python download_models.py
fi

echo "== link model files into ComfyUI model dirs =="
mkdir -p "$COMFY/models/unet" "$COMFY/models/text_encoders" "$COMFY/models/clip" \
         "$COMFY/models/vae" "$COMFY/models/loras"
# search recursively so it works whether files are flat or in HighNoise/LowNoise subfolders
find "$MODELS_SRC" -name '*.gguf'                    -exec ln -sf {} "$COMFY/models/unet/" \; 2>/dev/null || true
find "$MODELS_SRC" -iname '*umt5*'                   -exec ln -sf {} "$COMFY/models/text_encoders/" \; 2>/dev/null || true
find "$MODELS_SRC" -iname '*umt5*'                   -exec ln -sf {} "$COMFY/models/clip/" \; 2>/dev/null || true
find "$MODELS_SRC" -iname '*vae*'                    -exec ln -sf {} "$COMFY/models/vae/" \; 2>/dev/null || true
find "$MODELS_SRC" -iname '*lightning*'              -exec ln -sf {} "$COMFY/models/loras/" \; 2>/dev/null || true

echo "== linked models =="
ls -lh "$COMFY/models/unet" "$COMFY/models/loras" "$COMFY/models/vae" "$COMFY/models/text_encoders"

echo "bootstrap done. Start ComfyUI headless with:"
echo "  python $COMFY/main.py --listen 127.0.0.1 --port 8188 --lowvram &"
