#!/usr/bin/env bash
# OpenFlow Kaggle worker bootstrap.
# Assumes a private Kaggle Dataset with the 4-file model set is attached at
#   /kaggle/input/openflow-wan22/   (unet gguf, umt5 fp8 encoder, wan2.2 vae, lightning loras)
# Run this in a Kaggle GPU notebook cell with `!bash kaggle_bootstrap.sh`.
set -e

WORK=/kaggle/working
COMFY=$WORK/ComfyUI
MODELS_SRC=/kaggle/input/openflow-wan22

echo "== free some system RAM (Kaggle ~13GB, GGUF load spikes it) =="
python - <<'PY'
import psutil, gc, os
gc.collect()
print(f"RAM available: {psutil.virtual_memory().available/1e9:.1f} GB")
PY

echo "== install ComfyUI =="
if [ ! -d "$COMFY" ]; then
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "$COMFY"
fi
pip -q install -r "$COMFY/requirements.txt"

echo "== install custom nodes: ComfyUI-GGUF (city96) + VideoHelperSuite =="
cd "$COMFY/custom_nodes"
[ -d ComfyUI-GGUF ] || git clone --depth 1 https://github.com/city96/ComfyUI-GGUF
# Pin gguf: newer releases occasionally break against Kaggle's fixed Python.
pip -q install "gguf>=0.13.0" || pip -q install gguf==0.13.0
pip -q install -r ComfyUI-GGUF/requirements.txt || true
[ -d ComfyUI-VideoHelperSuite ] || git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
pip -q install -r ComfyUI-VideoHelperSuite/requirements.txt || true

echo "== link model files into ComfyUI's model dirs =="
mkdir -p "$COMFY/models/unet" "$COMFY/models/text_encoders" "$COMFY/models/clip" \
         "$COMFY/models/vae" "$COMFY/models/loras"
ln -sf "$MODELS_SRC"/*.gguf                       "$COMFY/models/unet/"            2>/dev/null || true
ln -sf "$MODELS_SRC"/*umt5*                       "$COMFY/models/text_encoders/"  2>/dev/null || true
ln -sf "$MODELS_SRC"/*umt5*                       "$COMFY/models/clip/"           2>/dev/null || true
ln -sf "$MODELS_SRC"/*vae*                        "$COMFY/models/vae/"            2>/dev/null || true
ln -sf "$MODELS_SRC"/*lightning*                  "$COMFY/models/loras/"          2>/dev/null || true

echo "== install cloudflared (for the tunnel, if backend is remote it is not needed here) =="
pip -q install requests psutil

echo "bootstrap done. Start ComfyUI headless with:"
echo "  python $COMFY/main.py --listen 127.0.0.1 --port 8188 --lowvram &"
