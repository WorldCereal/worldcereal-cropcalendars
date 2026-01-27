import importlib
import sys

MODULES = [
    "cdsapi",
    "xarray",
    "cdo",
    "IPython",
    "netCDF4",
    "osgeo",
    "skimage",
    "lmfit",
    "statsmodels",
    "sklearn",
    "seaborn",
    "geopandas",
    "rioxarray",
    "rasterio",
    "numba",
    "openeo",
    "spectral",
    "imageio",
    "pyproj",
    "tqdm_joblib",
]

failed = []
for name in MODULES:
    try:
        importlib.import_module(name)
        print(f"OK: {name}")
    except Exception as exc:
        print(f"FAIL: {name} -> {exc}")
        failed.append(name)

if failed:
    print("\nFailed imports:")
    for name in failed:
        print(f"- {name}")
    sys.exit(1)
