from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "supplementary_data_6_aggregated_results.xlsx"
OUTPUT_FILE = ROOT / "outputs" / "pollutant_distribution_by_airport.png"

df = pd.read_excel(INPUT_FILE, sheet_name="Emissions by Airport")
columns = ["HC (g)", "CO (g)", "NOₓ (g)", "nvPM (g)", "CO₂ (g)"]
labels = ["HC", "CO", r"NO$_x$", "nvPM", r"CO$_2$"]
data = [pd.to_numeric(df[c], errors="coerce").dropna().values for c in columns]

fig, ax = plt.subplots(figsize=(12, 7))
ax.boxplot(data, labels=labels, showfliers=False, patch_artist=True)
ax.set_yscale("log")
ax.set_xlabel("Pollutant")
ax.set_ylabel("Annual emission by airport (g, log scale)")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUTPUT_FILE, dpi=600, bbox_inches="tight")
print(f"Saved: {OUTPUT_FILE}")
