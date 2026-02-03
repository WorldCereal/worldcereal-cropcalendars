# WorldCereal crop calendars

[![Zenodo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17866271.svg)](https://doi.org/10.5281/zenodo.17866271)
[![Phase 2 paper (SSRN)](https://img.shields.io/badge/SSRN-5188749-blue)](https://ssrn.com/abstract=5188749)
[![Phase 1 paper (GIScience & Remote Sensing)](https://img.shields.io/badge/GIScience%20%26%20Remote%20Sensing-2022-blue)](https://doi.org/10.1080/15481603.2022.2079273)
[![CI](https://github.com/WorldCereal/worldcereal-cropcalendars/actions/workflows/ci.yml/badge.svg)](https://github.com/WorldCereal/worldcereal-cropcalendars/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Conda Env](https://img.shields.io/badge/conda%20env-ewoc--calendars-3ddc84)
![License](https://img.shields.io/badge/license-MIT-green)
![Last Commit](https://img.shields.io/github/last-commit/WorldCereal/worldcereal-cropcalendars)

This repo documents the workflow used to build the WorldCereal crop calendars and provides legacy outputs for reference.
All official inputs and outputs are published on Zenodo and must be used when reproducing results.

Primary dataset (inputs + outputs): DOI 10.5281/zenodo.17866271 (version v2, published Dec 7, 2025; last modified Jan 27, 2026)

## Data access (required)

1. Download the dataset from Zenodo using the DOI above.
2. Extract the files to a local folder (example: `DATA_ROOT=/path/to/zenodo_worldcereal`).
3. Use the files in that folder for all processing steps below.

Optional local example (ignored by git): this repo includes `data_root_example/` as a safe
place to unpack Zenodo files and validate paths. You can point `DATA_ROOT` there.

Recommended local layout after download/extract:

```
DATA_ROOT/
  auxiliar_data.zip
  NDVI_hants.zip
  summer_crops_dataset.csv
  winter_crops_dataset.csv
  S1_SOS_WGS84.tif
  S1_EOS_WGS84.tif
  S2_SOS_WGS84.tif
  S2_EOS_WGS84.tif
  Phase1_legacy_cropcalendars.zip
  doy_palette.qml
```

Unzip the archives before running:

```bash
unzip DATA_ROOT/auxiliar_data.zip -d DATA_ROOT/auxiliar_data
unzip DATA_ROOT/NDVI_hants.zip -d DATA_ROOT/NDVI_hants
```

Note: You can keep the legacy `cropcalendars_phase1/` and `cropcalendars_phase2/` folders for quick inspection,
but the authoritative data are on Zenodo.

### Zenodo

Total size: ~36.2 GB

```
auxiliar_data.zip
doy_palette.qml
Global Crop Calendar Dataset Documentation.pdf
NDVI_hants.zip
Phase1_legacy_cropcalendars.zip
S1_EOS_WGS84.tif
S1_SOS_WGS84.tif
S2_EOS_WGS84.tif
S2_SOS_WGS84.tif
summer_crops_dataset.csv
winter_crops_dataset.csv
```

Optional checksum verification:

```bash
md5 NDVI_hants.zip
# or (Linux)
md5sum NDVI_hants.zip
```

## Repository layout

- `src/crop_calendars/scripts/`: climate modeling scripts (XGBoost) to estimate SOS/EOS.
- `src/crop_calendars/necessary/`: auxiliary rasters and masks used by the scripts.
- `src/rs_process.py`: HANTS-based smoothing utilities for remote sensing time series.
- `src/hants_3d.py`: HANTS smoother that reads MODIS CMG NDVI from repo root.
- `cropcalendars_phase1/`: legacy outputs (Phase 1, Franch et al., 2022).
- `cropcalendars_phase2/`: legacy outputs (Phase 2, Moletto-Lobos et al., under review).

## Workflow overview

The workflow has three stages, in this order:

1) Climate modeling (SOS/EOS prediction, first iteration)
2) Remote sensing processing (HANTS + LSP extraction)
3) Climate modeling again (SOS/EOS prediction with LSP predictors, second iteration)

## Environment setup

Create the conda environment:

```bash
conda env create -f environment.yml
conda activate ewoc-calendars
```

### 1) Climate modeling (SOS/EOS prediction, first iteration)

Scripts:

- `src/crop_calendars/scripts/wc_sos_xgboost_1st_lsp.py`
- `src/crop_calendars/scripts/wc_eos_xgboost_1st_lsp.py`
- `src/crop_calendars/scripts/sc_sos_xgboost_1st_lsp.py`
- `src/crop_calendars/scripts/sc_eos_xgboost_1st_lsp.py`

Required inputs (from Zenodo):

- `winter_crops_dataset.csv` and `summer_crops_dataset.csv`
- `auxiliar_data.zip` (ERA5 data, masks, administrative boundaries, vegetation cover)

Recommended parameter mapping (paths):

```text
file_path_      -> DATA_ROOT
necessary_path  -> extracted auxiliar_data.zip folder
results_path    -> local output folder (feature selection)
model_output    -> local output folder (trained model)
```

What to edit in each script before running:

- `file_path_`: folder that contains `winter_crops_dataset.csv` and `summer_crops_dataset.csv`
- `necessary_path`: folder that contains the auxiliary rasters and vectors (from `auxiliar_data.zip`)
- `results_path`: where to write feature selection outputs
- `model_output`: where to save trained model files

Run example (one script at a time):

```bash
python src/crop_calendars/scripts/wc_sos_xgboost_1st_lsp.py
```

Outputs:

- Trained model files (JSON)
- Feature importance CSVs
- Predicted SOS/EOS values (per script logic)

These first-iteration calendars are used as the baseline window in the LSP step
(they define the SOS/EOS range used to constrain the MODIS CMG time series).

### 2) Remote sensing processing (HANTS + LSP extraction)

The MODIS CMG NDVI time series used in the paper are based on MODIS Aqua MYD09CMG.
The HANTS-smoothed output is published on Zenodo as `NDVI_hants.zip`.
If you need to reproduce the smoothing step from raw MODIS CMG, use `src/hants_3d.py`
and point it to the HDF files (MYD09CMG).

Example: run HANTS from MODIS CMG HDFs (outputs split into 20 COG chunks):

```bash
DATA_ROOT=/path/to/zenodo_worldcereal \
python src/hants_3d.py \
  --modis-cmg \
  --input-dir "$DATA_ROOT" \
  --modis-pattern "MYD09CMG*.hdf" \
  --split-count 20 \
  --output-format cog \
  --output-dir outputs/hants_cog \
  --output-prefix hants_myd09cmg
```

To apply HANTS to MODIS NDVI (high level):

1. Load the NDVI stack into a 3D array shaped `(nx, ny, nt)`.
2. Call `HANTS_3D` from `src/rs_process.py`.
3. Save the smoothed time series and proceed with feature extraction as in the modeling scripts.

LSP extraction (uses MODIS CMG, crop masks, and the 1st-iteration calendars):

- `src/lsp_world.py` reads MODIS CMG HDFs, applies QA masks, fills gaps, runs HANTS,
  and then extracts SOS/EOS/POK from the smoothed NDVI.
- The HANTS smoothing and LSP extraction are executed split-by-split (20 row-wise chunks)
  to keep memory usage stable.
- Environment variables used by `lsp_world.py` (defaults shown):
  - `DATA_ROOT` (default: `data_root_example`)
  - `MODIS_CMG_DIR` (default: `$DATA_ROOT/MODIS_CMG` or `$DATA_ROOT` if missing)
  - `WC_SOS_PATH` (default: `$DATA_ROOT/S1_SOS_WGS84.tif`)
  - `WC_EOS_PATH` (default: `$DATA_ROOT/S1_EOS_WGS84.tif`)
  - `CROP_MASK_PATH` (default: `$DATA_ROOT/auxiliar_data/CropCoverFraction_50km_3857.tif`)
  - `LSP_OUTPUT_DIR` (default: `outputs/lsp_world`)
- `LSP_USE_TERRA` (set to `1` to also include MOD09CMG)
  - `CONTINENTS_SHP` (default: `$DATA_ROOT/auxiliar_data/ne_10m_admin_0_sovereignty/ne_10m_admin_0_sovereignty.shp`)
  - `LSP_VAL_RATIO` (default: `0.3`, continent-stratified split)
  - `LSP_SPLIT_SEED` (default: `42`)

Validation points (70/30 split by continent):

- Place full points as GeoJSONs in `LSP_VALIDATION_DIR`:
  - `maize_points.geojson`
  - `wheat_points.geojson`
- On first run, `lsp_world.py` generates:
  - `maize_train.geojson` / `maize_validation.geojson`
  - `wheat_train.geojson` / `wheat_validation.geojson`
  using a 70/30 split stratified by continent.

After LSP metrics are generated, re-run the XGBoost scripts (second iteration) to
train the final SOS/EOS models using the LSP-derived predictors.

### 3) Climate modeling (SOS/EOS prediction, second iteration)

Re-run the same four scripts as in stage 1, now pointing to the LSP-derived inputs
and features generated in stage 2.

## End-to-end reproduction (paper pipeline)

Prerequisites:

- Zenodo dataset extracted to `DATA_ROOT`
- MODIS CMG HDFs (MYD09CMG, optionally MOD09CMG) for the study period
- Validation points:
  - `maize_points.geojson`
  - `wheat_points.geojson`
  placed in `LSP_VALIDATION_DIR` (default: `$DATA_ROOT/validation`)

Steps:

1) First iteration (climate-only baseline)

```bash
python src/crop_calendars/scripts/wc_sos_xgboost_1st_lsp.py
python src/crop_calendars/scripts/wc_eos_xgboost_1st_lsp.py
python src/crop_calendars/scripts/sc_sos_xgboost_1st_lsp.py
python src/crop_calendars/scripts/sc_eos_xgboost_1st_lsp.py
```

2) HANTS smoothing (MODIS CMG → HANTS)

```bash
DATA_ROOT=/path/to/zenodo_worldcereal \
python src/hants_3d.py \
  --modis-cmg \
  --input-dir "$DATA_ROOT" \
  --modis-pattern "MYD09CMG*.hdf" \
  --split-count 20 \
  --output-format cog \
  --output-dir outputs/hants_cog \
  --output-prefix hants_myd09cmg
```

3) LSP extraction (HANTS + phenology metrics)

```bash
DATA_ROOT=/path/to/zenodo_worldcereal \
python src/lsp_world.py
```

4) Second iteration (climate + LSP)

```bash
python src/crop_calendars/scripts/wc_sos_xgboost_1st_lsp.py
python src/crop_calendars/scripts/wc_eos_xgboost_1st_lsp.py
python src/crop_calendars/scripts/sc_sos_xgboost_1st_lsp.py
python src/crop_calendars/scripts/sc_eos_xgboost_1st_lsp.py
```

Note: the scripts in `src/crop_calendars/scripts/` require the path parameters
to be updated before running (see the section above).

## Citation

Phase 1:

Franch, B., Cintas, J., Becker-Reshef, I., Sanchez-Torres, M. J., Roger, J., Skakun, S., ... & Whitcraft, A. (2022).
Global crop calendars of maize and wheat in the framework of the WorldCereal project.
GIScience & Remote Sensing, 59(1), 885-913.
https://doi.org/10.1080/15481603.2022.2079273

Phase 2:

Moletto-Lobos, I. G., Franch, B., Guillem-Valls, A., Cyran, K., Kalecinski, N., Van Tricht, K., Vermote, E., Becker-Reshef, I.,
Nair, S., Degerickx, J., Butsko, C., Szantoi, Z., de Vos, K., Whitcraft, A.
Enhancing WorldCereal Crop Calendars with Land Surface Phenology and Machine Learning. Available at SSRN: https://ssrn.com/abstract=5188749
