import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import os

# Set Chinese font
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans SC"]
plt.rcParams["axes.unicode_minus"] = False

out_dir = r"H:\中国国际大学生创新创业计划\ui\docs\patent"
os.makedirs(out_dir, exist_ok=True)

fig, ax = plt.subplots(1, 1, figsize=(14, 16))
ax.set_xlim(0, 14)
ax.set_ylim(0, 16)
ax.axis("off")
ax.set_facecolor("white")

def draw_round_box(ax, x, y, w, h, color, border, text_lines, fontsize=8, title=None):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2",
                          facecolor=color, edgecolor=border, linewidth=1.8)
    ax.add_patch(box)
    if title:
        ax.text(x + w / 2, y + h - 0.35, title, ha="center", va="top",
                fontsize=fontsize + 1, fontweight="bold", fontfamily="monospace",
                color=border)
    for i, line in enumerate(text_lines):
        ax.text(x + w / 2, y + h - 0.9 - i * 0.55, line, ha="center", va="top",
                fontsize=fontsize, fontfamily="monospace", color="#37474F")

def draw_arrow(ax, x1, y1, x2, y2, color="#37474F", lw=2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw))

def draw_stage_label(ax, x, y, text, color):
    box = FancyBboxPatch((x - 1.5, y - 0.4), 3.0, 0.8,
                          boxstyle="round,pad=0.1",
                          facecolor=color, edgecolor=color, linewidth=1,
                          alpha=0.92)
    ax.add_patch(box)
    ax.text(x, y, text, ha="center", va="center", fontsize=9.5,
            fontweight="bold", color="white", fontfamily="monospace")

# Title
ax.text(7, 15.5, "图2  渐进式管线集成流程图", ha="center", fontsize=14,
        fontweight="bold", color="#1A237E")

# ============ Stage labels on left ============
# Entry
ax.text(0.8, 14.3, "START", fontsize=9, fontweight="bold", color="#1565C0",
        fontfamily="monospace", rotation=90, va="center")

# Stage 1 label
ax.text(13.5, 12, "Phase 1: w mode", fontsize=7.5, fontfamily="monospace",
        color="#2E7D32", va="center")
# Stage 2 label
ax.text(13.5, 7.8, "Phase 2: a mode", fontsize=7.5, fontfamily="monospace",
        color="#E65100", va="center")
# Stage 3+4 labels
ax.text(13.5, 3.5, "Phase 3-4:", fontsize=7.5, fontfamily="monospace",
        color="#C62828", va="center")
ax.text(13.5, 2.8, "a mode", fontsize=7.5, fontfamily="monospace",
        color="#C62828", va="center")

# ============ INPUT BOX ============
draw_round_box(ax, 2.5, 13.5, 9, 1.2, "#E3F2FD", "#1565C0", [
    "DICOM / NIfTI / .tiCi  Upload",
], fontsize=9, title="INPUT")

draw_arrow(ax, 7, 13.5, 7, 12.5)

# ============ PHASE 1 ============
draw_stage_label(ax, 7, 12.2, "PHASE 1", "#2E7D32")

draw_round_box(ax, 2, 9.3, 10, 2.6, "#E8F5E9", "#2E7D32", [
    "Create .tiCi  (mode: w)",
    "  write_metadata()        ->  /patient  +  /study",
    "  write_phase_images()    ->  /phases/*/images  [gzip-4]",
    "  write_provenance()      ->  /provenance",
], fontsize=8)

draw_arrow(ax, 7, 9.3, 7, 8.3)

# ============ PHASE 2 ============
draw_stage_label(ax, 7, 8, "PHASE 2", "#E65100")

draw_round_box(ax, 2, 6.3, 10, 1.4, "#FFF3E0", "#E65100", [
    "U-Net Segmentation  ->  binary masks per slice",
], fontsize=8, title="SEGMENTATION")

draw_arrow(ax, 7, 6.3, 7, 5.3)

draw_round_box(ax, 2, 3.8, 10, 1.2, "#FFF8E1", "#F9A825", [
    "append_phase_masks()  ->  /phases/0..N/masks  [lzf]",
], fontsize=8)

draw_arrow(ax, 7, 3.8, 3.5, 3.0)
draw_arrow(ax, 3.5, 3.0, 7, 1.8)

# ============ PHASE 3 ============
draw_stage_label(ax, 7, 2.6, "PHASE 3", "#6A1B9A")

draw_round_box(ax, 2, 1.3, 10, 1.0, "#F3E5F5", "#6A1B9A", [
    "IGTV Reconstruct  ->  ITV mask + mesh + volume",
], fontsize=8)

# Append IGTV
draw_arrow(ax, 10.5, 1.8, 10.5, 0.8)
draw_round_box(ax, 8.5, -0.5, 5, 1.0, "#FCE4EC", "#C62828", [
    "write_igtv()  ->  /igtv/*",
], fontsize=8)

# ============ PHASE 4 ============
draw_stage_label(ax, 7, 0.6, "PHASE 4", "#00695C")

draw_round_box(ax, 2, -0.8, 10, 0.9, "#E0F2F1", "#00695C", [
    "LSTM Predict  ->  centroids + observed + predicted",
], fontsize=8)

draw_arrow(ax, 7, -0.8, 7, -1.6)
draw_round_box(ax, 2, -2.6, 10, 0.9, "#E0F2F1", "#00695C", [
    "write_trajectory()  ->  /trajectory/*",
], fontsize=8)

# ============ FINAL ============
draw_arrow(ax, 7, -2.6, 7, -4.0)

success = FancyBboxPatch((2.5, -4.8), 9, 0.7, boxstyle="round,pad=0.15",
                          facecolor="#C8E6C9", edgecolor="#1B5E20", linewidth=2.5)
ax.add_patch(success)
ax.text(7, -4.45, "Single .tiCi: images + masks + IGTV + trajectory",
        ha="center", va="center", fontsize=9.5, fontweight="bold",
        fontfamily="monospace", color="#1B5E20")

# Bottom label
ax.text(7, -5.5, "Download / Exchange / Archive", ha="center", fontsize=8,
        fontfamily="monospace", color="#546E7A")

plt.tight_layout()
out2 = os.path.join(out_dir, "figure2_pipeline.png")
fig.savefig(out2, dpi=200, bbox_inches="tight", facecolor="white", edgecolor="none")
plt.close()
print(f"Figure 2 saved: {out2}")
