"""Generate the M0 metric-tree figure."""

from pathlib import Path
import matplotlib.pyplot as plt

NODES = {
    "oec": (0.50, 0.90, "Incremental contribution margin\nper eligible customer [OEC]"),
    "conv": (0.18, 0.63, "Incremental\ncompleted-order rate"),
    "margin": (0.50, 0.63, "Contribution margin\nper completed order"),
    "offer": (0.82, 0.63, "Expected redeemed-\noffer cost"),
    "base": (0.08, 0.30, "Baseline order\nprobability"),
    "response": (0.27, 0.30, "Treatment\nresponsiveness"),
    "aov": (0.42, 0.30, "Average\norder value"),
    "costs": (0.58, 0.30, "Variable costs +\nrefund/cancel drag"),
    "face": (0.74, 0.30, "Offer\nface value"),
    "redeem": (0.90, 0.30, "Redemption +\ncannibalization"),
}
EDGES = [("oec", "conv"), ("oec", "margin"), ("oec", "offer"),
         ("conv", "base"), ("conv", "response"), ("margin", "aov"),
         ("margin", "costs"), ("offer", "face"), ("offer", "redeem")]


def build_metric_tree(output_path: Path | None = None) -> Path:
    """Render the metric tree and return its path."""
    target = output_path or Path("reports/figures/metric_tree.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(14, 7.5))
    figure.patch.set_facecolor("#f7f4ed")
    axis.set_facecolor("#f7f4ed")
    axis.set(xlim=(0, 1), ylim=(0.12, 1))
    axis.axis("off")
    for parent, child in EDGES:
        x1, y1, _ = NODES[parent]
        x2, y2, _ = NODES[child]
        axis.plot([x1, x2], [y1 - 0.045, y2 + 0.045], color="#56616f", linewidth=1.8)
    for key, (x, y, label) in NODES.items():
        primary = key == "oec"
        axis.text(x, y, label, ha="center", va="center", fontsize=12 if primary else 10,
                  weight="bold" if primary else "normal", color="white" if primary else "#17212b",
                  bbox={"boxstyle": "round,pad=0.65", "facecolor": "#245953" if primary else "white",
                        "edgecolor": "#245953", "linewidth": 1.5})
    axis.text(0.5, 0.985, "M0 measurement contract: metric tree", ha="center", va="top",
              fontsize=17, weight="bold", color="#17212b")
    axis.text(0.5, 0.16, "All financial inputs are simulated placeholders until validated.",
              ha="center", fontsize=10, color="#7a3e22")
    figure.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return target


if __name__ == "__main__":
    print(build_metric_tree())
