"""Configuration. Everything comes from environment variables or the .env file; nothing secret is stored in code."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


DATA = Path(env("EXPOSIT_DATA", str(ROOT / "data"))).resolve()
MODELS = Path(env("EXPOSIT_MODELS", str(ROOT / "models"))).resolve()
HOST = env("EXPOSIT_HOST", "127.0.0.1")
PORT = int(env("EXPOSIT_PORT", "8600"))
ASSETS = Path(__file__).resolve().parent / "assets"
SEEDS = Path(__file__).resolve().parent / "seeds"
SKILLS = Path(__file__).resolve().parent / "skills"
WEB = ROOT / "web"

# Rendering defaults chosen for an 8 GB laptop without a GPU.
WIDTH = int(env("EXPOSIT_WIDTH", "1920"))
HEIGHT = int(env("EXPOSIT_HEIGHT", "1080"))
FPS = int(env("EXPOSIT_FPS", "30"))
X264_PRESET = env("EXPOSIT_X264_PRESET", "veryfast")
X264_CRF = env("EXPOSIT_X264_CRF", "19")
ENGINE_VERSION = "5"

for d in (DATA, DATA / "productions", DATA / "bridge" / "tasks", DATA / "bridge" / "results",
          DATA / "references", DATA / "cache" / "tts"):
    d.mkdir(parents=True, exist_ok=True)


def ffmpeg_exe() -> str:
    """Path to ffmpeg: EXPOSIT_FFMPEG, else the binary bundled with imageio-ffmpeg, else 'ffmpeg' on PATH."""
    explicit = env("EXPOSIT_FFMPEG")
    if explicit:
        return explicit
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"
