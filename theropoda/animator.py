"""Animator for Thera mascot states using generated GIFs from Thera/animations_web."""

from __future__ import annotations

import base64
import io
import os
from typing import Dict, Optional

from PIL import Image

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIM_WEB_DIR = os.path.join(ROOT_DIR, "assets", "thera")
FALLBACK_ICON = os.path.join(ROOT_DIR, "assets", "icon.png")

STATE_LABELS = {
    "sleeping": "💤 Dormindo (Idle)",
    "waking": "⚡ Acordando!",
    "running": "🏃 Correndo (Extraindo GEE)",
    "lot": "☕ Lote Grande! (+1000 polígonos)",
    "damage": "💥 Dano Crítico! (Erro)",
    "jetpack": "🚀 JetPack! (Análise de Tendência)",
    "tired": "😓 Cansado (Concluído)",
    "gonna_sleep": "🥱 Indo Dormir...",
    "analysing": "🔎 Analisando Dados",
}

FALLBACK_FILES = {
    "sleeping": "sleeping.jfif",
    "waking": "base.jfif",
    "running": "running.jfif",
    "lot": "running.jfif",
    "damage": "running.jfif",
    "jetpack": "flying.jfif",
    "tired": "base.jfif",
    "gonna_sleep": "sleeping.jfif",
    "analysing": "analysing.jfif",
}


def load_thera_sprites(size: int = 240) -> Dict[str, str]:
    """Load animated GIFs from Thera/animations_web (with .jfif fallback)."""
    encoded: Dict[str, str] = {}
    for state in STATE_LABELS:
        gif_path = os.path.join(ANIM_WEB_DIR, f"{state}.gif")
        if os.path.exists(gif_path):
            with open(gif_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            encoded[state] = f"data:image/gif;base64,{b64}"
            continue

        if os.path.exists(FALLBACK_ICON):
            with Image.open(FALLBACK_ICON) as img:
                img_rgb = img.convert("RGB").resize((size, size), Image.Resampling.NEAREST)
                buf = io.BytesIO()
                img_rgb.save(buf, format="PNG", optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                encoded[state] = f"data:image/png;base64,{b64}"
    return encoded


def resolve_thera_state(
    active_tab: str,
    running: bool,
    status_code: Optional[int],
    log_text: str,
    now: float,
    waking_until: float = 0.0,
    damage_until: float = 0.0,
    tired_until: float = 0.0,
    gonna_sleep_until: float = 0.0,
) -> str:
    """Determine the current Thera animation state from dashboard and pipeline context."""
    if active_tab in (
        "📊 Tabela & Tendências",
        "📈 Série Temporal por Polígono",
        "🗄️ Explorador do Banco SQLite",
    ):
        return "analysing"

    if running:
        if now < damage_until:
            return "damage"
        if now < waking_until:
            return "waking"
        if "Starting trend analysis" in log_text or "Preparing " in log_text:
            return "jetpack"
        if "Go take a coffee" in log_text:
            return "lot"
        return "running"

    if status_code == 0:
        if now < tired_until:
            return "tired"
        if now < gonna_sleep_until:
            return "gonna_sleep"

    return "sleeping"


def count_log_errors(log_text: str) -> int:
    """Count error lines in the pipeline log."""
    return sum(
        1
        for line in log_text.splitlines()
        if "| ERROR" in line or "Traceback (most recent call last)" in line
    )


def build_thera_canvas_html(sprites: Dict[str, str], state: str, size: int = 220) -> str:
    """Build a crisp pixel-art HTML widget displaying the selected animation GIF."""
    label = STATE_LABELS.get(state, state)
    img_src = sprites.get(state) or next(iter(sprites.values()), "")
    border_color = "#ff4b4b" if state == "damage" else ("#00e5ff" if state == "jetpack" else "#1f4e78")

    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;font-family:ui-monospace,Consolas,monospace;">
      <img src="{img_src}" width="{size}" height="{size}"
        style="border-radius:12px;border:2px solid {border_color};background:#081629;
               image-rendering:pixelated;box-shadow:0 4px 14px rgba(0,0,0,0.45);" />
      <div style="margin-top:6px;font-size:12px;font-weight:600;color:#58a6ff;text-align:center;">{label}</div>
    </div>
    """
