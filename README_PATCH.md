# v1.0.2 code patch

This patch is intended to replace the corresponding files in the public repository without uploading the large full runway dataset.

## Replace these files

- `code/01_aircraft_runway_coupled_model.m`
- `code/02_cci_calculation.m`
- `code/03_pso_cci_calibration.m`
- `code/05_national_emission_inventory.py`

The existing `code/04_surrogate_model.py` and figure scripts do not require changes in this patch.

## What changed

### 01 coupled FEM model
The large finite-element runway input is no longer assumed to be public. The script resolves repository-relative paths and stops with an explicit message when `data/confidential/Run_result_input.mat` is absent. This prevents a reviewer from receiving a misleading file-not-found error.

### 02 CCI calculation
The default `RUN_MODE = "demo"` uses only `data/example_roughness_profile.mat`; the full runway-profile dataset is not required. `RUN_MODE = "batch"` is reserved for a local manuscript-scale rerun. Missing batch data produce a clear error rather than a silent synthetic fallback.

### 03 PSO calibration
Repository-relative paths, deterministic random seed, modern MATLAB I/O, output saving, and strict input checks were added. Missing calibration/runway inputs are never silently replaced by fabricated data.

### 05 national emission inventory
The script now accepts the English column names in `aircraft_emission_factors.xlsx`, interprets declared factor units, converts reported pollutant masses to grams, and skips/logs missing frequency matches instead of assigning `frequency = 1`.

## Important note on nvPM
The public emission-factor workbook declares nvPM factors as `mg/MJ`, whereas the earlier aggregated workbook labels nvPM results as `g`. This patch follows the declared source unit and converts `mg/MJ` to `g/MJ` before reporting mass in grams. Before replacing manuscript nvPM values, verify the unit against the original emission-factor source.

## Recommended public-data statement
The full finite-element runway structural input and full roughness-profile set are not bundled because of file-size and/or data-access restrictions. A representative non-confidential roughness profile is provided to demonstrate the CCI computational workflow. Full manuscript-scale calculations require the locally authorized inputs described in the code comments.
