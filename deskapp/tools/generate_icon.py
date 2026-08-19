"""Generate the macOS app icon for TradingAgents.

Output:
    deskapp/app_bundle/Resources/icon.icns  (used by .app)

Design:
    - Rounded square background with blue → teal gradient
    - White line chart (5 points trending up) — represents trading
    - 5 white nodes at each point — the multi-agent pipeline
    - Last node highlighted in amber — the final trade decision

Run:
    python deskapp/tools/generate_icon.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication


# All sizes macOS expects in an .icns file
SIZES: list[tuple[int, int]] = [
    (16, 1),       # 16x16
    (16, 2),       # 16x16 @2x  → 32x32
    (32, 1),       # 32x32
    (32, 2),       # 32x32 @2x  → 64x64
    (64, 1),       # 64x64
    (64, 2),       # 64x64 @2x  → 128x128
    (128, 1),      # 128x128
    (128, 2),      # 128x128 @2x → 256x256
    (256, 1),      # 256x256
    (256, 2),      # 256x256 @2x → 512x512
    (512, 1),      # 512x512
    (512, 2),      # 512x512 @2x → 1024x1024
]


def make_icon(size: int) -> QPixmap:
    """Render the TradingAgents icon at the given (square) px size."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    # ─── Background: rounded square with gradient ───
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#1e40af"))  # blue-800
    grad.setColorAt(1.0, QColor("#0891b2"))  # cyan-600
    radius = size * 0.22
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, size, size, radius, radius)

    # ─── Chart line: 5 points trending up ───
    margin = size * 0.18
    w = size - 2 * margin
    h = size - 2 * margin
    points = [
        (margin + w * 0.00, margin + h * 0.78),
        (margin + w * 0.25, margin + h * 0.55),
        (margin + w * 0.50, margin + h * 0.60),
        (margin + w * 0.75, margin + h * 0.35),
        (margin + w * 1.00, margin + h * 0.22),
    ]

    # Line
    pen = QPen(QColor("white"))
    pen.setWidth(max(2, int(size * 0.045)))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        p.drawLine(int(x1), int(y1), int(x2), int(y2))

    # Nodes (agents)
    node_r = max(2, int(size * 0.07))
    p.setBrush(QColor("white"))
    p.setPen(Qt.NoPen)
    for x, y in points:
        p.drawEllipse(int(x - node_r), int(y - node_r), node_r * 2, node_r * 2)

    # Highlight last node (the decision) — amber ring
    last_x, last_y = points[-1]
    p.setBrush(Qt.NoBrush)
    ring_pen = QPen(QColor("#fbbf24"))  # amber-400
    ring_pen.setWidth(max(2, int(size * 0.035)))
    p.setPen(ring_pen)
    ring_r = node_r * 1.7
    p.drawEllipse(int(last_x - ring_r), int(last_y - ring_r),
                  int(ring_r * 2), int(ring_r * 2))

    p.end()
    return pix


def build_iconset() -> Path:
    """Generate all PNG sizes and assemble into a .icns file."""
    # iconutil expects a directory ending in .iconset
    iconset_dir = Path("/tmp/TradingAgents.iconset")
    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir()

    # Generate PNGs
    for size, scale in SIZES:
        actual = size * scale
        pix = make_icon(actual)
        if scale == 1:
            name = f"icon_{size}x{size}.png"
        else:
            name = f"icon_{size}x{size}@2x.png"
        out = iconset_dir / name
        if not pix.save(str(out), "PNG"):
            raise RuntimeError(f"failed to save {out}")

    # Convert to .icns using macOS iconutil
    icns_out = Path("/Users/sbb/TradingAgents/deskapp/app_bundle/Resources/icon.icns")
    icns_out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_out)],
        check=True,
    )
    return icns_out


def main() -> None:
    # QPixmap requires a QApplication (or QGuiApplication) to be alive.
    _app = QApplication.instance() or QApplication(sys.argv)

    print("▶ Generating TradingAgents icon...")
    print("  Rendering 12 PNG sizes...")
    for size, scale in SIZES:
        actual = size * scale
        print(f"    {actual}x{actual}px")

    icns = build_iconset()
    print(f"✓ Icon saved: {icns}")
    print(f"  file size: {icns.stat().st_size} bytes")
    print()
    print("Rebuild the .app to apply:")
    print("  ./deskapp/build_app.sh")


if __name__ == "__main__":
    main()
