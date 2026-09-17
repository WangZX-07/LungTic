import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
import os

# Set Chinese font
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans SC"]
plt.rcParams["axes.unicode_minus"] = False

out_dir = r"H:\中国国际大学生创新创业计划\ui\docs\patent"
os.makedirs(out_dir, exist_ok=True)

fig, ax = plt.subplots(1, 1, figsize=(16, 20))
ax.set_xlim(0, 16)
ax.set_ylim(0, 20)
ax.axis("off")
ax.set_facecolor("white")


def draw_box(ax, x, y, w, h, text, color="#E3F2FD", border="#1565C0",
             text_color="#0D47A1", fontsize=9, bold=True):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                          facecolor=color, edgecolor=border, linewidth=1.5)
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    lines = text.split("\n")
    line_h = h / (len(lines) + 0.5)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - line_h - i * line_h * 0.85, line,
                ha="center", va="center", fontsize=fontsize, color=text_color,
                fontweight=weight, fontfamily="sans-serif")


def draw_container(ax, x, y, w, h, text, color="#E8EAF6", border="#3F51B5"):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2",
                          facecolor=color, edgecolor=border, linewidth=2)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h - 0.3, text, ha="center", va="top",
            fontsize=10, color="#1A237E", fontweight="bold", fontfamily="sans-serif")


def draw_arrow(ax, x1, y1, x2, y2, color="#546E7A", lw=1.5):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw))


# Title (use sans-serif for Chinese)
ax.text(8, 19.3, "图1  .tiCi 格式层次化存储结构示意图", ha="center", fontsize=14,
        fontweight="bold", color="#1A237E")

# Root container
draw_container(ax, 3, 17.5, 10, 1.8,
               ".TICI File (HDF5 Container)\nMAGIC: \\x89TICI\\r\\n\\x1a\\n  VERSION: 1.0",
               color="#E8EAF6", border="#283593")

# /patient group
draw_box(ax, 0.5, 14, 3.2, 3.2,
         "/patient\n----------\n@patient_id\n@patient_name\n@patient_sex\n@patient_age",
         color="#E3F2FD", border="#1565C0")

# /study group
draw_box(ax, 4.5, 14, 3.5, 3.2,
         "/study\n----------\n@study_uid\n@study_date\n@modality\n@phase_count\n@rows / cols",
         color="#E3F2FD", border="#1565C0")

# /provenance group
draw_box(ax, 8.8, 14, 3.5, 3.2,
         "/provenance\n----------\n@source_type\n@files_count\n@converter_ver\n@conversion_date",
         color="#FFF3E0", border="#E65100")

# /phases container
draw_container(ax, 0.5, 7, 15, 6.2,
               "/phases  (N groups)",
               color="#E8F5E9", border="#2E7D32")

# phase_0
draw_box(ax, 1, 8, 4.5, 4.6, "", color="#C8E6C9", border="#43A047", fontsize=8, bold=False)
ax.text(3.25, 12, "phase_0/", ha="center", fontsize=9, fontweight="bold",
        fontfamily="monospace", color="#1B5E20")
ax.text(3.25, 11.1, "  images  (Z,H,W) float32", ha="center", fontsize=8,
        fontfamily="monospace", color="#2E7D32")
ax.text(3.25, 10.5, "    [gzip level=4]", ha="center", fontsize=7,
        fontfamily="monospace", color="#66BB6A")
ax.text(3.25, 9.7, "  masks   (Z,H,W) uint8", ha="center", fontsize=8,
        fontfamily="monospace", color="#2E7D32")
ax.text(3.25, 9.1, "    [lzf] (optional)", ha="center", fontsize=7,
        fontfamily="monospace", color="#66BB6A")

# phase_1
draw_box(ax, 6, 8, 4.5, 4.6, "", color="#C8E6C9", border="#43A047", fontsize=8, bold=False)
ax.text(8.25, 12, "phase_1/", ha="center", fontsize=9, fontweight="bold",
        fontfamily="monospace", color="#1B5E20")
ax.text(8.25, 11.1, "  images  (Z,H,W) float32", ha="center", fontsize=8,
        fontfamily="monospace", color="#2E7D32")
ax.text(8.25, 10.5, "    [gzip level=4]", ha="center", fontsize=7,
        fontfamily="monospace", color="#66BB6A")
ax.text(8.25, 9.7, "  masks   (Z,H,W) uint8", ha="center", fontsize=8,
        fontfamily="monospace", color="#2E7D32")
ax.text(8.25, 9.1, "    [lzf] (optional)", ha="center", fontsize=7,
        fontfamily="monospace", color="#66BB6A")

# phase_N
draw_box(ax, 11, 8, 4, 4.6, "", color="#C8E6C9", border="#43A047", fontsize=8, bold=False)
ax.text(13, 12, "phase_N/", ha="center", fontsize=9, fontweight="bold",
        fontfamily="monospace", color="#1B5E20")
ax.text(13, 11.1, "  ...", ha="center", fontsize=9,
        fontfamily="monospace", color="#2E7D32")
ax.text(13, 10.3, "  images + masks", ha="center", fontsize=8,
        fontfamily="monospace", color="#2E7D32")

# /igtv group
draw_box(ax, 0.5, 0.3, 5.5, 3.5, "", color="#FCE4EC", border="#C62828", fontsize=8)
ax.text(3.25, 3.15, "/igtv", ha="center", fontsize=10, fontweight="bold",
        fontfamily="monospace", color="#B71C1C")
ax.text(3.25, 2.3, "@volume_cc   (Float)", ha="center", fontsize=8,
        fontfamily="monospace", color="#C62828")
ax.text(3.25, 1.7, "@method      (String)", ha="center", fontsize=8,
        fontfamily="monospace", color="#C62828")
ax.text(3.25, 1.1, "mask (Z,Y,X) uint8 [lzf]", ha="center", fontsize=8,
        fontfamily="monospace", color="#C62828")
ax.text(3.25, 0.5, "mesh (OBJ text)", ha="center", fontsize=8,
        fontfamily="monospace", color="#C62828")

# /trajectory group
draw_box(ax, 7, 0.3, 5.5, 3.5, "", color="#F3E5F5", border="#6A1B9A", fontsize=8)
ax.text(9.75, 3.15, "/trajectory", ha="center", fontsize=10, fontweight="bold",
        fontfamily="monospace", color="#4A148C")
ax.text(9.75, 2.5, "@prediction_model", ha="center", fontsize=8,
        fontfamily="monospace", color="#7B1FA2")
ax.text(9.75, 1.9, "centroids  (N,3) float32", ha="center", fontsize=8,
        fontfamily="monospace", color="#7B1FA2")
ax.text(9.75, 1.3, "observed   (7,3) float32", ha="center", fontsize=8,
        fontfamily="monospace", color="#7B1FA2")
ax.text(9.75, 0.7, "predicted  (3,3) float32", ha="center", fontsize=8,
        fontfamily="monospace", color="#7B1FA2")

# Arrows: root -> branches
for cx in [2.1, 6.25, 10.55]:
    draw_arrow(ax, cx, 17.5, cx, 17.22, color="#90A4AE")

# Arrow: study -> phases
draw_arrow(ax, 6.25, 14, 6.25, 13.25, color="#90A4AE")

# Arrows to igtv and trajectory
draw_arrow(ax, 3.25, 7, 3.25, 3.85, color="#90A4AE")
draw_arrow(ax, 9.75, 7, 9.75, 3.85, color="#90A4AE")

# Legend box bottom-right
draw_box(ax, 13, 0.3, 2.5, 3.5, "", color="#ECEFF1", border="#78909C", fontsize=7)
ax.text(14.25, 3.2, "Compression", ha="center", fontsize=8, fontweight="bold",
        fontfamily="monospace", color="#37474F")
lines_legend = [
    "images: gzip-4",
    "masks:  lzf",
    "igtv:   lzf",
    "traj:   none",
    "attr:   none",
]
for i, line in enumerate(lines_legend):
    ax.text(14.25, 2.5 - i * 0.45, line, ha="center", fontsize=7,
            fontfamily="monospace", color="#546E7A")

plt.tight_layout()
out1 = os.path.join(out_dir, "figure1_hierarchy.png")
fig.savefig(out1, dpi=200, bbox_inches="tight", facecolor="white", edgecolor="none")
plt.close()
print(f"Figure 1 saved: {out1}")
