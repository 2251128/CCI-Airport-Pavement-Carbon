# Reproducibility package

This repository contains the analysis code and non-confidential/example data used to document the aircraft-runway roughness and airport ground-emission workflow.

## Code

- `code/01_aircraft_runway_coupled_model.m`: aircraft-runway coupled dynamic model. The finite-element runway structural input is confidential and is therefore not redistributed.
- `code/02_cci_calculation.m`: CCI calculation workflow.
- `code/03_pso_cci_calibration.m`: PSO-based CCI parameter calibration. This script retains the original call to `calculate_CCI`; the helper function was not included in the files supplied for this release and must be added if this calibration is rerun.
- `code/04_surrogate_model.py`: physics-informed surrogate model; an illustrative synthetic dataset is provided.
- `code/05_national_emission_inventory.py`: national airport emission inventory using phase-specific emission factors. The bundled default input folder contains one demonstration airport.

## Data

- `data/demo_airport/AAT_demo_airport.xlsx`: demonstration airport input in the same structure used by the inventory code.
- `data/national_aircraft_frequency.xlsx`: national airport-aircraft frequency data (Supplementary Data 1).
- `data/aircraft_emission_factors.xlsx`: aircraft emission factors for take-off and idle/low-thrust conditions.
- `data/supplementary_data_6_aggregated_results.xlsx`: aggregated results used by the plotting scripts.
- `data/example_roughness_profile.mat`: example roughness profile.
- `data/example_surrogate_data.csv`: synthetic data for demonstrating the surrogate-model workflow.
- `data/scenario_projection_example.csv`: illustrative scenario data only; these values are not the manuscript scenario results.

The underlying airport roughness measurements and the full finite-element runway structural inputs are subject to confidentiality restrictions and are not redistributed.

## Figures

The scripts in `figures/` read the aggregated Supplementary Data 6 workbook directly where applicable. The scenario figure uses clearly labelled illustrative data because the original scenario aggregation was spreadsheet-based.

## National emission classification

The inventory applies an operational speed criterion of 36 km/h to select phase-specific emission factors: records below the threshold use idle/low-thrust factors, while records at or above the threshold use take-off factors. The threshold is an analysis criterion used in this inventory and is not presented as a universal industry boundary.

## Running the Python examples

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

MATLAB scripts require the relevant MATLAB toolboxes used by the source code.
