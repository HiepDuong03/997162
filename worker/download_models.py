"""Download the Wan 2.2 A14B model set into a target dir (default /kaggle/temp/models).

Run this on the Kaggle worker at session start. It downloads straight from
HuggingFace to Kaggle's large scratch disk (/kaggle/temp, ~50GB) — NOT to
/kaggle/working (~20GB, too small for these files).

Filenames written here match backend/adapters/wan22_a14b.json. LoRA filenames in
the lightx2v repo vary, so we list the repo and pattern-match high/low × t2v/i2v.

Env:
  MODELS_DIR   target dir (default /kaggle/temp/models)
  QUANT        GGUF quant to fetch (default Q4_K_M; use Q3_K_M to save ~20% disk)
  HF_TOKEN     optional, for faster/authenticated downloads
"""
import os
import sys

from huggingface_hub import hf_hub_download, list_repo_files

MODELS_DIR = os.environ.get("MODELS_DIR", "/kaggle/temp/models")
QUANT = os.environ.get("QUANT", "Q4_K_M")
os.makedirs(MODELS_DIR, exist_ok=True)


def fetch(repo: str, filename: str, rename: str):
    dest = os.path.join(MODELS_DIR, rename)
    if os.path.exists(dest) and os.path.getsize(dest) > 1_000_000:
        print(f"skip (exists): {rename}")
        return
    path = hf_hub_download(repo_id=repo, filename=filename, local_dir=MODELS_DIR)
    if os.path.abspath(path) != os.path.abspath(dest):
        os.replace(path, dest)
    print(f"OK: {rename}  ({os.path.getsize(dest)/1e9:.1f} GB)")


def fetch_gguf_experts(repo: str, prefix: str):
    """Grab the HighNoise and LowNoise GGUF for the chosen quant from a repo."""
    files = list_repo_files(repo)
    for noise in ("HighNoise", "LowNoise"):
        match = [f for f in files if noise in f and QUANT in f and f.endswith(".gguf")]
        if not match:
            raise RuntimeError(f"no {noise} {QUANT} gguf in {repo}; available: "
                               + ", ".join(f for f in files if f.endswith('.gguf')))
        fetch(repo, match[0], f"{prefix}-{noise.lower().replace('noise','')}noise-{QUANT}.gguf")


def fetch_lightning_loras():
    repo = "lightx2v/Wan2.2-Lightning"
    files = list_repo_files(repo)
    loras = [f for f in files if f.endswith(".safetensors")]
    wanted = {
        ("t2v", "high"): "wan2.2-lightning-t2v-a14b-4steps-highnoise.safetensors",
        ("t2v", "low"): "wan2.2-lightning-t2v-a14b-4steps-lownoise.safetensors",
        ("i2v", "high"): "wan2.2-lightning-i2v-a14b-4steps-highnoise.safetensors",
        ("i2v", "low"): "wan2.2-lightning-i2v-a14b-4steps-lownoise.safetensors",
    }
    for (mode, noise), rename in wanted.items():
        cand = [f for f in loras
                if mode in f.lower() and noise in f.lower() and "a14b" in f.lower()]
        if not cand:
            print(f"WARN: no LoRA matched {mode}/{noise}. Repo files:\n  "
                  + "\n  ".join(loras))
            continue
        fetch(repo, cand[0], rename)


def main():
    # UNet experts
    fetch_gguf_experts("QuantStack/Wan2.2-T2V-A14B-GGUF", "wan2.2-t2v-a14b")
    fetch_gguf_experts("QuantStack/Wan2.2-I2V-A14B-GGUF", "wan2.2-i2v-a14b")
    # text encoder + vae
    fetch("Comfy-Org/Wan_2.2_ComfyUI_Repackaged",
          "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
          "umt5_xxl_fp8_e4m3fn_scaled.safetensors")
    fetch("Comfy-Org/Wan_2.2_ComfyUI_Repackaged",
          "split_files/vae/wan2.2_vae.safetensors", "wan2.2_vae.safetensors")
    # lightning loras
    fetch_lightning_loras()
    print(f"\nAll models in {MODELS_DIR}:")
    for f in sorted(os.listdir(MODELS_DIR)):
        p = os.path.join(MODELS_DIR, f)
        if os.path.isfile(p):
            print(f"  {f}  {os.path.getsize(p)/1e9:.1f} GB")


if __name__ == "__main__":
    sys.exit(main())
