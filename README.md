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

### Zenodo v2 file list (from record you shared)

Total size: ~36.2 GB

```
auxiliar_data.zip              md5: edcdf748755de3fdc4998ea0dfe3dd59
doy_palette.qml                md5: 172e03ac430b60f5cf9ba42af89f13c0
Global Crop Calendar Dataset Documentation.pdf
                               md5: a4de1e3308d902c57e18298fd091cd86
NDVI_hants.zip                 md5: d65a8c9a7d16d5b482525368910cdaf4
Phase1_legacy_cropcalendars.zip
                               md5: f69007a846daba161a427f8620db1c54
S1_EOS_WGS84.tif               md5: 70d7974efa14064c805650b46c995f82
S1_SOS_WGS84.tif               md5: 5e38e38953bae61fd2b6cea38baa2e91
S2_EOS_WGS84.tif               md5: 9ac26f53e32de774d89390aa9bbe7eea
S2_SOS_WGS84.tif               md5: 397c4d0d90426f3def01c4e55d9cc668
summer_crops_dataset.csv       md5: 8c2338cc1e0c5c9507cd0872dce3a37c
winter_crops_dataset.csv       md5: 45a9f9f7a2b38d957cb4345d45fb6ee5
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

The workflow has two stages, in this order:

1) Climate modeling (SOS/EOS prediction)
2) Remote sensing processing (time-series smoothing)

## Environment setup

Create the conda environment:

```bash
conda env create -f environment.yml
conda activate ewoc-calendars
```

### 1) Climate modeling (SOS/EOS prediction)

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
results_path    -> local output folder (feature selection CSVs)
model_output    -> local output folder (trained model JSONs)
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

### 2) Remote sensing processing (time-series smoothing)

The MODIS CMG NDVI time series used in the paper are published on Zenodo as `NDVI_hants.zip`.
This is the HANTS-smoothed output (already processed).
Unzip it in the repo root so the stack lives under `NDVI_hants/`.
If you need to reproduce the smoothing step from raw MODIS CMG, use the HANTS implementation in `src/rs_process.py`.

MODIS CMG example (reads from repo root `NDVI_hants/`):

```bash
python src/hants_3d.py --input-dir NDVI_hants --output outputs/hants_smoothed.npy
```

To apply HANTS to MODIS NDVI:

1. Load the NDVI stack into a 3D array shaped `(nx, ny, nt)`.
2. Call `HANTS_3D` from `src/rs_process.py`.
3. Save the smoothed time series and proceed with feature extraction as in the modeling scripts.

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
