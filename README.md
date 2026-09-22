# Reproducibility package

This repository contains the analysis code and non-confidential/example data used to document the aircraft-runway roughness and airport ground-emission workflow.

## Scope of the public archive

The public archive is designed to provide the computational workflow without redistributing the very large or access-restricted runway structural dataset. A representative non-confidential roughness profile is included so that the lightweight CCI workflow can be executed directly.

The manuscript-scale finite-element runway input and the complete runway-profile/calibration datasets are **not** bundled. Scripts that require those inputs now perform explicit preflight checks and stop with an informative message instead of silently substituting synthetic data.

## Code

- `code/01_aircraft_runway_coupled_model.m` — aircraft-runway coupled finite-element model. Requires the local large/restricted file `data/confidential/Run_result_input.mat`.
- `code/02_cci_calculation.m` — CCI calculation workflow. The default `RUN_MODE = "demo"` uses only `data/example_roughness_profile.mat`; `RUN_MODE = "batch"` is reserved for the full local dataset.
- `code/03_pso_cci_calibration.m` — PSO-based CCI parameter-calibration workflow. A full rerun requires the locally authorized calibration workbooks, runway profiles, and the original `calculate_CCI.m` helper used in the calibration campaign. The public script performs a strict input check and does not fabricate missing calibration results.
- `code/04_surrogate_model.py` — physics-informed surrogate-model demonstration using the bundled illustrative dataset.
- `code/05_national_emission_inventory.py` — national airport emission-inventory workflow using phase-specific emission factors. The bundled default airport folder contains one demonstration airport.

## Data

- `data/example_roughness_profile.mat` — representative non-confidential roughness profile for the lightweight CCI example.
- `data/demo_airport/AAT_demo_airport.xlsx` — demonstration airport input in the same structure used by the emission-inventory code.
- `data/aircraft_emission_factors.xlsx` — aircraft emission factors for take-off and idle/low-thrust conditions.
- `data/national_aircraft_frequency.xlsx` — airport-aircraft frequency data used by the inventory workflow, subject to the licensing conditions of the source dataset.
- `data/example_surrogate_data.csv` — synthetic/illustrative dataset for the surrogate-model example.
- `data/scenario_projection_example.csv` — illustrative scenario data; not the manuscript scenario results.
- `data/supplementary_data_6_aggregated_results.xlsx` — aggregated results used by the plotting scripts.

## National emission classification

The inventory uses an analysis threshold of **36 km/h** to select phase-specific emission factors: records below the threshold use idle/low-thrust factors, whereas records at or above the threshold use take-off factors. This threshold is an analysis criterion for the present inventory and is not presented as a universal industry boundary.

The revised inventory code also applies two safeguards:

1. a missing airport-aircraft frequency is logged and skipped rather than replaced by an arbitrary default frequency; and
2. factor units declared in the source workbook are interpreted explicitly and reported pollutant masses are normalized to grams.

**nvPM note:** the bundled factor workbook declares nvPM factors as `mg/MJ`. The revised code therefore converts these factors to `g/MJ` before reporting nvPM mass in grams. The original source metadata should be checked before changing manuscript-level nvPM values.

## Running the public examples

### Python

```bash
pip install -r requirements.txt
python code/04_surrogate_model.py
python code/05_national_emission_inventory.py
python figures/01_plot_emissions_by_functional_area.py
python figures/02_plot_pollutant_distribution_by_airport.py
python figures/03_plot_cectol_by_region.py
python figures/04_plot_cectol_by_province.py
python figures/05_plot_scenario_projection_example.py
```

### MATLAB lightweight CCI example

Open MATLAB at any working directory and run:

```matlab
run('code/02_cci_calculation.m')
```

The script resolves paths from its own location and writes the demonstration results to `outputs/`.

For the full manuscript-scale finite-element or calibration rerun, provide the locally authorized large/restricted inputs described in the comments of `code/01_aircraft_runway_coupled_model.m` and `code/03_pso_cci_calibration.m`.

## Reproducibility statement

The public archive provides runnable examples for the lightweight CCI, surrogate-model, national-emission, and plotting workflows using non-confidential or illustrative data. The complete airport pavement measurements and finite-element runway structural inputs are not redistributed because of file-size and/or data-access restrictions. Their omission does not cause the public scripts to silently substitute manuscript results.
