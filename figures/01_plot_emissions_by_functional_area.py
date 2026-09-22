from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "supplementary_data_6_aggregated_results.xlsx"
OUTPUT_FILE = ROOT / "outputs" / "emissions_by_functional_area.png"

df = pd.read_excel(INPUT_FILE, sheet_name="Emissions by Functional Area")
df = df.iloc[:, :6].dropna(how="all")
areas = df["Functional area"].astype(str).tolist()
columns = ["HC (g)", "CO (g)", "NOₓ (g)", "nvPM (g)", "CO₂ (g)"]
labels = ["HC", "CO", r"NO$_x$", "nvPM", r"CO$_2$"]

x = np.arange(len(areas))
bar_width = 0.14
fig, ax = plt.subplots(figsize=(12, 8))
for i, (col, label) in enumerate(zip(columns, labels)):
    ax.bar(x + i * bar_width, df[col].astype(float).values, width=bar_width, label=label)
ax.set_yscale("log")
ax.set_xlabel("Functional area")
ax.set_ylabel("Emission (g, log scale)")
ax.set_xticks(x + bar_width * (len(columns)-1)/2)
ax.set_xticklabels(areas, rotation=10)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(title="Pollutants")
fig.tight_layout()
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUTPUT_FILE, dpi=600, bbox_inches="tight")
print(f"Saved: {OUTPUT_FILE}")
