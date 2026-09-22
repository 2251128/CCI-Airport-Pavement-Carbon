from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "scenario_projection_example.csv"
OUTPUT_FILE = ROOT / "outputs" / "scenario_projection_example.png"

df = pd.read_csv(INPUT_FILE)
fig, ax = plt.subplots(figsize=(12, 7))
ax.fill_between(df["year"], df["lower_g"], df["upper_g"], alpha=0.25, label="Illustrative uncertainty range")
ax.plot(df["year"], df["co2_emission_g"], linewidth=2.5, label="Illustrative CO2 scenario")
ax.set_xlabel("Year")
ax.set_ylabel("CO2 emission (g)")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend()
fig.tight_layout()
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUTPUT_FILE, dpi=600, bbox_inches="tight")
print(f"Saved: {OUTPUT_FILE}")
