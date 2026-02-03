import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine
from osgeo import gdal

from src.rs_process import HANTS_3D
from remote_sensing.aux_functions import apply_qa_moydga09_cmg


def _read_stack(folder: Path, pattern: str, max_files: int | None) -> tuple[np.ndarray, dict, list[Path]]:
    files = sorted(folder.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files found in {folder} matching {pattern}")
    if max_files is not None:
        files = files[:max_files]
    arrays = []
    profile = None
    for path in files:
        with rasterio.open(path) as src:
            arr = src.read(1).astype(float)
            nodata = src.nodata
            if nodata is not None:
                arr[arr == nodata] = np.nan
            arrays.append(arr)
            if profile is None:
                profile = src.profile
    stack = np.stack(arrays, axis=-1)
    return stack, profile, files


def _extract_date_cmg(filename: str) -> datetime:
    date_str = Path(filename).name.split(".")[1][1:]
    return datetime.strptime(date_str, "%Y%j")


def _read_modis_cmg_ndvi(path: Path) -> np.ndarray:
    ds_4326 = gdal.Open(str(path))
    if ds_4326 is None:
        raise RuntimeError(f"Failed to open MODIS CMG file: {path}")
    sds = ds_4326.GetSubDatasets()
    ds_refl_b01_red = sds[0][0]
    ds_refl_b02_nir = sds[1][0]
    ds_qa = sds[19][0]
    ds_sza = sds[7][0]
    ds_vza = sds[8][0]

    refl_b01_red_cmg = gdal.Open(ds_refl_b01_red).ReadAsArray()
    refl_b02_nir_cmg = gdal.Open(ds_refl_b02_nir).ReadAsArray()
    ndvi = (refl_b02_nir_cmg - refl_b01_red_cmg) / (refl_b02_nir_cmg + refl_b01_red_cmg)
    qa = gdal.Open(ds_qa).ReadAsArray()
    sza = gdal.Open(ds_sza).ReadAsArray() / 100
    vza = gdal.Open(ds_vza).ReadAsArray() / 100
    mask = apply_qa_moydga09_cmg(qa, sza, vza, aerosol=False)
    return ndvi * mask


def _read_modis_cmg_stack(
    folder: Path,
    pattern: str,
    max_files: int | None,
) -> tuple[np.ndarray, list[datetime], list[Path], dict]:
    files = sorted(folder.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files found in {folder} matching {pattern}")
    if max_files is not None:
        files = files[:max_files]
    arrays = []
    dates = []
    profile = None
    for path in files:
        if profile is None:
            ds_4326 = gdal.Open(str(path))
            sds = ds_4326.GetSubDatasets()
            ds_refl_b01_red = sds[0][0]
            with rasterio.open(ds_refl_b01_red) as src:
                profile = {
                    "crs": src.crs,
                    "transform": src.transform,
                    "width": src.width,
                    "height": src.height,
                }
        arrays.append(_read_modis_cmg_ndvi(path))
        dates.append(_extract_date_cmg(str(path)))
    stack = np.stack(arrays, axis=-1)
    return stack, dates, files, profile


def _write_cog(path: Path, data_3d: np.ndarray, base_profile: dict, row_offset: int = 0) -> None:
    if data_3d.ndim != 3:
        raise ValueError("data_3d must be (rows, cols, bands).")
    height, width, count = data_3d.shape
    transform = base_profile["transform"]
    if row_offset:
        transform = Affine(transform.a, transform.b, transform.c,
                           transform.d, transform.e, transform.f + transform.e * row_offset)
    profile = {
        "driver": "COG",
        "dtype": "float32",
        "count": count,
        "height": height,
        "width": width,
        "crs": base_profile["crs"],
        "transform": transform,
        "nodata": np.nan,
        "compress": "deflate",
        "predictor": 2,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.moveaxis(data_3d.astype(np.float32), -1, 0))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run HANTS_3D on MODIS CMG NDVI stack from repo root NDVI_hants/"
    )
    parser.add_argument(
        "--input-dir",
        default="NDVI_hants",
        help="Folder (relative to repo root) with MODIS CMG NDVI GeoTIFFs",
    )
    parser.add_argument(
        "--modis-cmg",
        action="store_true",
        help="Read MODIS CMG HDF (MYD09CMG/MOD09CMG) and compute NDVI on the fly",
    )
    parser.add_argument(
        "--modis-pattern",
        default="MYD09CMG*.hdf",
        help="Glob pattern for MODIS CMG HDFs when --modis-cmg is set",
    )
    parser.add_argument(
        "--pattern",
        default="*.tif*",
        help="Glob pattern for NDVI files (default: *.tif*)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional cap on number of time slices to load",
    )
    parser.add_argument(
        "--base-period-len",
        type=float,
        default=None,
        help="Seasonal period length; defaults to number of time steps",
    )
    parser.add_argument(
        "--n-freq",
        type=int,
        default=3,
        help="Number of harmonics",
    )
    parser.add_argument(
        "--low",
        type=float,
        default=-0.2,
        help="Lower valid bound for NDVI",
    )
    parser.add_argument(
        "--high",
        type=float,
        default=1.0,
        help="Upper valid bound for NDVI",
    )
    parser.add_argument(
        "--fit-error-tolerance",
        type=float,
        default=0.05,
        help="Residual tolerance for HANTS weights",
    )
    parser.add_argument(
        "--split-count",
        type=int,
        default=20,
        help="Number of row-wise splits to process independently",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for split outputs when --split-count > 1",
    )
    parser.add_argument(
        "--output-prefix",
        default="hants_smoothed",
        help="Prefix for split outputs when --split-count > 1",
    )
    parser.add_argument(
        "--output-format",
        choices=("npy", "cog"),
        default="npy",
        help="Output format for smoothed stacks (npy or cog)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output .npy path for smoothed stack",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    input_dir = repo_root / args.input_dir

    if args.modis_cmg:
        stack, dates, files, profile = _read_modis_cmg_stack(input_dir, args.modis_pattern, args.max_files)
    else:
        stack, profile, files = _read_stack(input_dir, args.pattern, args.max_files)
        dates = None
    nt = stack.shape[-1]
    base_period_len = args.base_period_len if args.base_period_len is not None else float(nt)

    split_count = max(1, args.split_count)
    splits = np.array_split(stack, split_count, axis=0)
    smoothed_splits = []
    for split in splits:
        smoothed_splits.append(
            HANTS_3D(
                split,
                ts=np.arange(nt, dtype=float),
                base_period_len=base_period_len,
                n_freq=args.n_freq,
                low=args.low,
                high=args.high,
                fit_error_tolerance=args.fit_error_tolerance,
                dod=1,
                outliers_to_reject="None",
                weight_scheme="huber",
                max_iterations=25,
                min_improvement=1e-5,
            )
        )
    smoothed = np.vstack(smoothed_splits)

    print(f"Loaded {len(files)} files from {input_dir}")
    print(f"Stack shape: {stack.shape} -> smoothed: {smoothed.shape}")

    if split_count > 1:
        if args.output_dir is None:
            raise ValueError("When --split-count > 1, set --output-dir to store split outputs.")
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        split_outputs = np.array_split(smoothed, split_count, axis=0)
        row_offsets = np.cumsum([0] + [s.shape[0] for s in split_outputs[:-1]])
        for idx, (split, row_offset) in enumerate(zip(split_outputs, row_offsets)):
            if args.output_format == "cog":
                if profile is None:
                    raise ValueError("COG output requires a georeferenced input profile.")
                out_path = output_dir / f"{args.output_prefix}_part_{idx:02d}.tif"
                _write_cog(out_path, split, profile, row_offset=int(row_offset))
            else:
                out_path = output_dir / f"{args.output_prefix}_part_{idx:02d}.npy"
                np.save(out_path, split)
        if dates is not None:
            np.save(output_dir / f"{args.output_prefix}_dates.npy", np.array(dates, dtype="datetime64[D]"))
        print(f"Saved {split_count} split outputs to {output_dir}")
    elif args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if args.output_format == "cog":
            if profile is None:
                raise ValueError("COG output requires a georeferenced input profile.")
            _write_cog(output_path, smoothed, profile)
        else:
            np.save(output_path, smoothed)
            if dates is not None:
                np.save(output_path.with_suffix(".dates.npy"), np.array(dates, dtype="datetime64[D]"))
        print(f"Saved smoothed stack to {output_path}")


if __name__ == "__main__":
    main()
