import argparse
from pathlib import Path

import numpy as np
import rasterio

from src.rs_process import HANTS_3D


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
        "--output",
        default=None,
        help="Optional output .npy path for smoothed stack",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    input_dir = repo_root / args.input_dir

    stack, profile, files = _read_stack(input_dir, args.pattern, args.max_files)
    nt = stack.shape[-1]
    base_period_len = args.base_period_len if args.base_period_len is not None else float(nt)

    smoothed = HANTS_3D(
        stack,
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

    print(f"Loaded {len(files)} files from {input_dir}")
    print(f"Stack shape: {stack.shape} -> smoothed: {smoothed.shape}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, smoothed)
        print(f"Saved smoothed stack to {output_path}")


if __name__ == "__main__":
    main()
