import os
import sys
from pathlib import Path
sys.path.append(os.getcwd())
import rasterio
from rasterio.warp import calculate_default_transform, reproject
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.crs import CRS
import numpy as np
import pandas as pd
from glob import glob
from itertools import groupby
import numba as nb
import geopandas as gpd
from rasterio.features import geometry_mask
from osgeo import gdal
from datetime import datetime, timedelta, time
import gc
import concurrent.futures
from itertools import groupby
from remote_sensing.aux_functions import (HANTS_3d_alterver, HANTS_3d_withoutsos_eos,
                                          fill_nan_linear_debug, export_to_cog, fill_with_nearest_within_distance,
                                          retrieve_LSP, apply_qa_moydga09_cmg, export_to_cog_multiband)


# Function to adjust years and convert DOY to date for SOS and EOS arrays
def adjust_years_and_convert_to_date(sos_array, eos_array):
    extend_time = timedelta(30)
    sos_dates = np.empty(sos_array.shape, dtype='object')  # Use dtype='object' to allow None or datetime objects
    eos_dates = np.empty(eos_array.shape, dtype='object')
    los_dates = np.empty(eos_array.shape, dtype=np.int16)

    for i in nb.prange(sos_array.shape[0]):
        for j in nb.prange(sos_array.shape[1]):
            sos_doy = int(sos_array[i, j])  # Convert NumPy int64 to Python int
            eos_doy = int(eos_array[i, j])  # Convert NumPy int64 to Python int

            # Check for 0 values and skip or handle them
            if sos_doy == 0 or eos_doy == 0:
                sos_dates[i, j] = None  # Assign None to indicate invalid/missing date
                eos_dates[i, j] = None
                continue  # Skip the rest of the processing for this pair

            # Determine the years based on SOS and EOS comparison
            if sos_doy > eos_doy:
                sos_year = 2020
                eos_year = 2021
            else:
                sos_year = 2021
                eos_year = 2021

            # Convert DOY to date for SOS and EOS, adjusting for Python int type
            sos_date = datetime(sos_year, 1, 1) + timedelta(days=sos_doy - 1) - extend_time
            eos_date = datetime(eos_year, 1, 1) + timedelta(days=eos_doy - 1) + extend_time

            los_date = (eos_date - sos_date).days
            if los_date > 300:
                print('anomalous season found, shortening')
                sos_date = datetime(sos_year, 1, 1) + timedelta(days=sos_doy - 1) + extend_time
                eos_date = datetime(eos_year, 1, 1) + timedelta(days=eos_doy - 1) - extend_time
                los_date = (eos_date - sos_date).days
            ### PATCH for extension
            extend_time_eos = timedelta(180)
            eos_date = datetime(eos_year, 1, 1) + timedelta(days=eos_doy - 1) + extend_time_eos
            sos_dates[i, j] = sos_date
            eos_dates[i, j] = eos_date
            los_dates[i, j] = los_date

    return sos_dates, eos_dates, los_dates


def get_unique_dates(date_array):
    # Filter out None values and convert datetime objects to date (if not already)
    valid_dates = {date.date() for date in date_array.flatten() if date is not None}

    # Convert the set back to a sorted list
    unique_dates_sorted = sorted(list(valid_dates))

    return unique_dates_sorted


def date_to_index(dates, start_date):
    indices = np.empty(dates.shape, dtype=np.float64)
    for i in range(dates.shape[0]):
        for j in range(dates.shape[1]):
            if dates[i, j] is not None:
                delta = datetime.combine(dates[i, j], datetime.min.time()) - start_date
                indices[i, j] = delta.days
            else:
                indices[i, j] = np.nan
    return indices


# Function to convert indices to DOY
def index_to_doy(indices, start_date):
    start_doy = start_date.timetuple().tm_yday  # DOY for start_date

    # Initialize an array of the same shape as indices to hold the DOY values
    doys = np.empty(indices.shape, dtype=np.float64)

    for i in range(indices.shape[0]):
        for j in range(indices.shape[1]):
            if not np.isnan(indices[i, j]):
                # Calculate the date corresponding to the index
                date_for_index = start_date + timedelta(days=int(indices[i, j]))

                # Convert the date to DOY
                doys[i, j] = date_for_index.timetuple().tm_yday
            else:
                doys[i, j] = np.nan  # Preserve NaN values

    return doys


data_root = Path(os.getenv("DATA_ROOT", "data_root_example")).resolve()
modis_dir = Path(os.getenv("MODIS_CMG_DIR", str(data_root / "MODIS_CMG")))
if not modis_dir.exists():
    modis_dir = data_root
path_export = Path(os.getenv("LSP_OUTPUT_DIR", "outputs/lsp_world")).resolve()
path_plots = Path(os.getenv("LSP_PLOTS_DIR", "outputs/lsp_plots")).resolve()
os.makedirs(path_plots, exist_ok=True)
os.makedirs(path_export, exist_ok=True)
path_sos_wc = Path(os.getenv("WC_SOS_PATH", str(data_root / "S1_SOS_WGS84.tif")))
path_eos_wc = Path(os.getenv("WC_EOS_PATH", str(data_root / "S1_EOS_WGS84.tif")))
path_world_ww = Path(os.getenv("CROP_MASK_PATH", str(data_root / "auxiliar_data" / "CropCoverFraction_50km_3857.tif")))
val_path = Path(os.getenv("LSP_VALIDATION_DIR", str(data_root / "validation")))
continents_shp = Path(os.getenv("CONTINENTS_SHP", str(data_root / "auxiliar_data" / "ne_10m_admin_0_sovereignty" / "ne_10m_admin_0_sovereignty.shp")))
split_seed = int(os.getenv("LSP_SPLIT_SEED", "42"))
split_ratio = float(os.getenv("LSP_VAL_RATIO", "0.3"))

if not path_sos_wc.exists():
    raise FileNotFoundError(f"Missing WC_SOS_PATH: {path_sos_wc}")
if not path_eos_wc.exists():
    raise FileNotFoundError(f"Missing WC_EOS_PATH: {path_eos_wc}")
if not path_world_ww.exists():
    raise FileNotFoundError(f"Missing CROP_MASK_PATH: {path_world_ww}")
if not continents_shp.exists():
    raise FileNotFoundError(f"Missing CONTINENTS_SHP: {continents_shp}")

wc_sos = rasterio.open(path_sos_wc)  # .read(1)
wc_eos = rasterio.open(path_eos_wc)  # .read(1)

use_terra = os.getenv("LSP_USE_TERRA", "0") == "1"
mod_images = glob(str(modis_dir / "*MOD09CMG*.hdf")) if use_terra else []
myd_images = glob(str(modis_dir / "*MYD09CMG*.hdf"))


def extract_date_cmg(filename):
    """Extracts the date from the filename."""
    date_str = filename.split('/')[-1].split('.')[1][1:]
    return datetime.strptime(date_str, '%Y%j')


def extract_values(data_array, geom, affine_transform):
    all_touched = True  # or False, depending on your needs
    mask = geometry_mask([geom], invert=True, transform=affine_transform,
                         out_shape=(data_array.shape[1], data_array.shape[2]), all_touched=all_touched)

    # Use the mask to extract data from each time slice in the 3D array
    extracted_data = np.array([data_array[t][mask] for t in range(data_array.shape[0])])
    return extracted_data


product_version = 'v2-5'
years = ['2021']
year = years[0]
# for year in years:
past_year = str(int(year) - 1)
if myd_images:
    epsg4326_tiff_path = myd_images[0]
elif mod_images:
    epsg4326_tiff_path = mod_images[0]
else:
    raise FileNotFoundError(f"No MODIS CMG HDFs found in {modis_dir}")


def _split_by_continent(gdf: gpd.GeoDataFrame, continents: gpd.GeoDataFrame, seed: int, val_ratio: float):
    if gdf.empty:
        return gdf.copy(), gdf.copy()
    if gdf.crs != continents.crs:
        continents = continents.to_crs(gdf.crs)
    joined = gpd.sjoin(gdf, continents[["CONTINENT", "geometry"]], how="left", predicate="within")
    joined["CONTINENT"] = joined["CONTINENT"].fillna("Unknown")
    train_parts = []
    val_parts = []
    rng = np.random.default_rng(seed)
    for continent, part in joined.groupby("CONTINENT"):
        idx = part.index.to_numpy()
        if len(idx) == 1:
            train_parts.append(part)
            continue
        n_val = max(1, int(np.ceil(len(idx) * val_ratio)))
        val_idx = rng.choice(idx, size=n_val, replace=False)
        val_mask = part.index.isin(val_idx)
        val_parts.append(part[val_mask])
        train_parts.append(part[~val_mask])
    train_gdf = gpd.GeoDataFrame(pd.concat(train_parts).drop(columns=["index_right"]), crs=gdf.crs)
    val_gdf = gpd.GeoDataFrame(pd.concat(val_parts).drop(columns=["index_right"]), crs=gdf.crs)
    return train_gdf, val_gdf


def _load_or_build_validation_points(val_dir: Path, base_name: str, continents: gpd.GeoDataFrame):
    val_file = val_dir / f"{base_name}_validation.geojson"
    train_file = val_dir / f"{base_name}_train.geojson"
    full_file = val_dir / f"{base_name}_points.geojson"
    if val_file.exists():
        return gpd.read_file(val_file)
    if not full_file.exists():
        raise FileNotFoundError(f"Missing {val_file} and {full_file}")
    os.makedirs(val_dir, exist_ok=True)
    gdf = gpd.read_file(full_file)
    train_gdf, val_gdf = _split_by_continent(gdf, continents, seed=split_seed, val_ratio=split_ratio)
    train_gdf.to_file(train_file, driver="GeoJSON")
    val_gdf.to_file(val_file, driver="GeoJSON")
    return val_gdf


continents_gdf = gpd.read_file(continents_shp)
gdf_maize = _load_or_build_validation_points(val_path, "maize", continents_gdf)
gdf_wheat = _load_or_build_validation_points(val_path, "wheat", continents_gdf)
latitude_thresholds = [-90, -54, -18, 18, 54, 90]
# Open the sinusoidal TIFF
with rasterio.open(path_world_ww) as src:
    worldcereal_array = src.read(1)  # Assuming you want the first band
    worldcereal_transform = src.transform
    worldcereal_crs = src.crs
# Open the EPSG:4326 TIFF
ds_4326 = gdal.Open(epsg4326_tiff_path)
sds = ds_4326.GetSubDatasets()
ds_refl_b01_red = sds[0][0]  # red band

refl_b01_red = gdal.Open(ds_refl_b01_red)
# Get the width and height of the dataset
tgt_width = refl_b01_red.RasterXSize
tgt_height = refl_b01_red.RasterYSize
# Get the affine transformation coefficients
target_transform_gdal = refl_b01_red.GetGeoTransform()
target_resolution = target_transform_gdal[1]  # pixel width
# Get the CRS using the GetProjection method, which returns a WKT (Well-Known Text)
target_crs_wkt = refl_b01_red.GetProjection()
target_crs = CRS.from_wkt(target_crs_wkt)
# Create an Affine transform object for rasterio
target_transform = Affine.from_gdal(*target_transform_gdal)
refl_b01_red = None

# Calculate the transform and dimensions for the reprojection
transform, width, height = calculate_default_transform(
    worldcereal_crs, target_crs, src.width, src.height, *src.bounds, resolution=target_resolution)

# Now, reproject the sinusoidal array to match the EPSG:4326 array exactly
ww_mask = np.empty(shape=(tgt_height, tgt_width), dtype=worldcereal_array.dtype)

wc_sos_array = np.empty(shape=(tgt_height, tgt_width), dtype=worldcereal_array.dtype)
wc_eos_array = np.empty(shape=(tgt_height, tgt_width), dtype=worldcereal_array.dtype)

# Reproject the data
reproject(
    source=worldcereal_array,
    destination=ww_mask,
    src_transform=worldcereal_transform,
    src_crs=worldcereal_crs,
    dst_transform=target_transform,
    dst_crs=target_crs,
    resampling=Resampling.nearest  # Adjust resampling method as needed
)

reproject(
    source=wc_sos.read(1),
    destination=wc_sos_array,
    src_transform=wc_sos.transform,
    src_crs=wc_sos.crs,
    dst_transform=target_transform,
    dst_crs=target_crs,
    resampling=Resampling.nearest  # Adjust resampling method as needed
)

reproject(
    source=wc_eos.read(1),
    destination=wc_eos_array,
    src_transform=wc_eos.transform,
    src_crs=wc_sos.crs,
    dst_transform=target_transform,
    dst_crs=target_crs,
    resampling=Resampling.nearest  # Adjust resampling method as needed
)
# remove unvalid values from resample
wc_sos_array[wc_sos_array < 0] = 0
wc_sos_array[wc_sos_array > 366] = 0
wc_eos_array[wc_eos_array < 0] = 0
wc_eos_array[wc_eos_array > 366] = 0
(sos_dates, eos_dates,
 los_dates) = adjust_years_and_convert_to_date(wc_sos_array.astype(int),
                                               wc_eos_array.astype(int))
los_dates_float = los_dates.astype(np.float32)
los_dates_float[los_dates_float <= 0] = np.nan
los_dates_float[los_dates_float > 366] = np.nan
los_dates_float_binary = np.copy(los_dates_float) * 0 + 1

"""
sos_dates = sos_dates * los_dates_float_binary
eos_dates = eos_dates * los_dates_float_binary
"""
# just for query data
unique_sos_dates = np.array(get_unique_dates(sos_dates))
unique_eos_dates = np.array(get_unique_dates(eos_dates))
wc_sos_array = wc_sos_array.astype(np.float32)
# wc_sos_array[wc_sos_array < 100] = np.nan
doy_start_int = int(np.nanmin(wc_sos_array)) - 50
doy_end_int = int(np.nanmax(wc_eos_array)) + 50
if doy_end_int > 365:
    doy_end_int = doy_end_int - 365
doy_start = str(doy_start_int)  # 27)  # 27 = rmse model
doy_end = str(int(np.nanmax(wc_eos_array)) + 50)  # 27)  # 27 = rmse model
# mask_ww
ww_mask = ww_mask.astype(np.float32)
ww_mask[ww_mask <= 25] = np.nan
ww_mask[ww_mask > 100] = np.nan

ww_mask_binary = np.copy(ww_mask) * 0 + 1

# Define your date interval
start_date = datetime.combine(unique_sos_dates.min(), time())  # .strftime('%Y%j')
end_date = datetime.combine(unique_eos_dates.max(), time())  # .strftime('%Y%j')

# Convert sos_dates and eos_dates to indices
sos_indices = date_to_index(sos_dates, start_date)
eos_indices = date_to_index(eos_dates, start_date)

combined_images = [(path, 'MOD') for path in mod_images] + [(path, 'MYD') for path in myd_images]

# Filter images by date interval
filtered_images = [img for img in combined_images if start_date <= extract_date_cmg(img[0]) <= end_date]
filtered_images.sort(key=lambda x: extract_date_cmg(x[0]))


def process_images(images):
    """Process a list of images for the same date with rasterio, add the array to result_arrays, and store the date."""
    arrays = []
    for image in images:
        try:
            ds_4326 = gdal.Open(image[0])
            sds = ds_4326.GetSubDatasets()
            ds_refl_b01_red = sds[0][0]  # red band
            ds_refl_b02_nir = sds[1][0]  # nir band
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
            arrays.append(ndvi * mask)
        except Exception as exc:
            print(f"error reading {image[0]}: {exc}")
    date = extract_date_cmg(images[0][0])
    if not arrays:
        return None, date
    if len(arrays) == 1:
        return arrays[0], date
    mean_array = np.nanmean(np.stack(arrays, axis=0), axis=0)
    return mean_array, date


# Process images grouped by date within the filtered list
#for key, group in groupby(filtered_images, key=lambda x: extract_date_cmg(x[0])):
#    process_images(list(group))

grouped_images = [list(group) for key, group in groupby(filtered_images, key=lambda x: extract_date_cmg(x[0]))]

# Use ProcessPoolExecutor to process images in parallel
with concurrent.futures.ProcessPoolExecutor(max_workers=60) as executor:
    # Map process_images to each group of images
    results = list(executor.map(process_images, grouped_images))

# ola = zonal_stats(gdf_maize, los_dates_float,
#                         stats=['mean'], affine=target_transform, all_touched=True, geojson_out=True)

# ndvi = np.array(result_arrays)

# Lists to store the results
result_arrays = []
result_dates = []

for arrays, date in results:
    if arrays is None:
        continue
    result_arrays.append(arrays)
    result_dates.append(date)
    print(f"Added array for {date}")

number_of_splits = 20
# Height of each segment (assuming equal division)
segment_height = tgt_height / number_of_splits
# Original affine transform parameters
A, B, C, D, E, F = (target_transform[0], target_transform[1], target_transform[2],
                    target_transform[3], target_transform[4],
                    target_transform[5])  # Assuming you have these from your data

split_query = 0
l_split_sos1 = []
l_split_eos1 = []
l_split_pok1 = []

l_split_sos2 = []
l_split_eos2 = []
l_split_pok2 = []

l_split_sos3 = []
l_split_eos3 = []
l_split_pok3 = []
formatted_dates = [date.strftime('%Y-%m-%d') for date in result_dates]

l_ndvi_max = []
for split_query in range(0, number_of_splits):
    new_F = F + E * segment_height * split_query
    # Create the new affine transform for the segment
    segment_affine = Affine(A, B, C, D, E, new_F)
    split1 = []
    for result_array in result_arrays:
        split1.append(np.split(result_array, number_of_splits)[split_query])

    ndvi = np.array(split1)

    # land_mask = np.nanmean(ndvi, axis = 0) #* 0 + 1
    # land_mask[land_mask <= 0] = np.nan
    # land_mask = land_mask * 0 + 1
    ndays = ndvi.shape[0]

    # ww_mask_binary1 = np.split(ww_mask_binary,number_of_splits)[split_query]
    # ww_mask_binary_repeated = np.tile(ww_mask_binary1[None, :, :], (ndays, 1, 1))

    sos_indices1 = np.split(sos_indices, number_of_splits)[split_query]
    eos_indices1 = np.split(eos_indices, number_of_splits)[split_query]

    sos_dates_split = np.split(sos_dates, number_of_splits)[split_query]
    eos_dates_split = np.split(eos_dates, number_of_splits)[split_query]

    ndvi[ndvi == 0] = np.nan
    # ndvi = ndvi * ww_mask_binary_repeated
    rearranged_ndvi = np.moveaxis(ndvi, 0, -1)
    # Step 2: Count the number of valid (non-NaN) values along the third axis
    valid_counts = np.count_nonzero(~np.isnan(rearranged_ndvi), axis=2)
    # Step 3: Identify slices with 3 or fewer valid values
    mask = valid_counts <= 7
    # Step 4: Replace these identified slices with NaN
    # Expanding mask to the shape of arr for broadcasting
    expanded_mask = mask[:, :, np.newaxis]
    # Use np.where to replace only the selected slices
    rearranged_ndvi = np.where(expanded_mask, np.nan, rearranged_ndvi)

    ndvi_filled = fill_nan_linear_debug(rearranged_ndvi)


    # ndvi_hants_filled = fill_nan_linear_debug(ndvihants)
    # ndvi_hants_filled = HANTS_3d_alterver(ndvi_filled,
    #                                      sos_dates_split, eos_dates_split,
    #                                      sos_indices1, eos_indices1)
    ndvi_hants_filled = HANTS_3d_withoutsos_eos(ndvi_filled)

    # remove all those values where ndvi difference is too low
    crs_code = 'EPSG:4326'
    export_to_cog_multiband(np.moveaxis(ndvi_hants_filled, -1, 0), segment_affine, target_crs,
                            os.path.join(path_export,
                                         f'NDVI_fix-hants_{year}_{product_version}_{str(split_query)}.tif'),
                            band_names=formatted_dates)

    ndvi_max = np.nanpercentile(ndvi_hants_filled, 95, axis=2)
    ndvi_min = np.nanpercentile(ndvi_hants_filled, 5, axis=2)
    ndvi_diff = ndvi_max - ndvi_min
    ndvi_diff[ndvi_diff >= 0.1] = 1
    ndvi_diff[ndvi_diff < 0.1] = np.nan
    # available options, percentile, AUC, derivative
    # https://www.sciencedirect.com/science/article/pii/S0303243419301278, perc=30
    model = 'percentile'
    percentile = 30
    print(f'modeliling using: {model}, at {percentile}')
    (start_of_season1, peak_of_season1,
     end_of_season1, start_of_season2, peak_of_season2,
     end_of_season2, start_of_season3, peak_of_season3,
     end_of_season3) = retrieve_LSP(ndvi_hants_filled, model, percentile=percentile)
    # Season 1
    peak_of_season_doy1 = index_to_doy(peak_of_season1, start_date)
    start_of_season_doy1 = index_to_doy(start_of_season1, start_date)
    end_of_season_doy1 = index_to_doy(end_of_season1, start_date)
    # remove nodata
    peak_of_season_doy1 = peak_of_season_doy1.astype(np.float32)  # * ndvi_diff
    start_of_season_doy1 = start_of_season_doy1.astype(np.float32)  # * ndvi_diff
    end_of_season_doy1 = end_of_season_doy1.astype(np.float32)  # * ndvi_diff
    detector_nodata_pok = np.nanmin(peak_of_season1)
    detector_nodata_seos = np.nanmin(start_of_season1)
    start_of_season_doy1[start_of_season1 == detector_nodata_seos] = np.nan
    peak_of_season_doy1[peak_of_season1 == detector_nodata_pok] = np.nan
    end_of_season_doy1[end_of_season1 == detector_nodata_seos] = np.nan

    # Season 2
    peak_of_season_doy2 = index_to_doy(peak_of_season2, start_date)
    start_of_season_doy2 = index_to_doy(start_of_season2, start_date)
    end_of_season_doy2 = index_to_doy(end_of_season2, start_date)
    # remove nodata
    peak_of_season_doy2 = peak_of_season_doy2.astype(np.float32)  # * ndvi_diff
    start_of_season_doy2 = start_of_season_doy2.astype(np.float32)  # * ndvi_diff
    end_of_season_doy2 = end_of_season_doy2.astype(np.float32)  # * ndvi_diff
    detector_nodata_pok = np.nanmin(peak_of_season2)
    detector_nodata_seos = np.nanmin(start_of_season2)
    start_of_season_doy2[start_of_season2 == detector_nodata_seos] = np.nan
    peak_of_season_doy2[peak_of_season2 == detector_nodata_pok] = np.nan
    end_of_season_doy2[end_of_season2 == detector_nodata_seos] = np.nan

    # Season 3

    peak_of_season_doy3 = index_to_doy(peak_of_season3, start_date)
    start_of_season_doy3 = index_to_doy(start_of_season3, start_date)
    end_of_season_doy3 = index_to_doy(end_of_season3, start_date)
    # remove nodata
    peak_of_season_doy3 = peak_of_season_doy3.astype(np.float32)  # * ndvi_diff
    start_of_season_doy3 = start_of_season_doy3.astype(np.float32)  # * ndvi_diff
    end_of_season_doy3 = end_of_season_doy3.astype(np.float32)  # * ndvi_diff
    detector_nodata_pok = np.nanmin(peak_of_season3)
    detector_nodata_seos = np.nanmin(start_of_season3)
    start_of_season_doy3[start_of_season3 == detector_nodata_seos] = np.nan
    peak_of_season_doy3[peak_of_season3 == detector_nodata_pok] = np.nan
    end_of_season_doy3[end_of_season3 == detector_nodata_seos] = np.nan

    # plot_2d_show(start_of_season_doy)
    l_split_sos1.append(start_of_season_doy1)
    l_split_pok1.append(peak_of_season_doy1)
    l_split_eos1.append(end_of_season_doy1)

    l_split_sos2.append(start_of_season_doy2)
    l_split_pok2.append(peak_of_season_doy2)
    l_split_eos2.append(end_of_season_doy2)

    l_split_sos3.append(start_of_season_doy3)
    l_split_pok3.append(peak_of_season_doy3)
    l_split_eos3.append(end_of_season_doy3)

    l_ndvi_max.append(ndvi_max)
    del ndvi
    del ndvi_hants_filled
    del ndvi_filled
    # del ndvihants
    del rearranged_ndvi
    # del ww_mask_binary1
    del split1
    gc.collect()

sos_stack1 = np.vstack(l_split_sos1)
pok_stack1 = np.vstack(l_split_pok1)
eos_stack1 = np.vstack(l_split_eos1)

sos_stack2 = np.vstack(l_split_sos2)
pok_stack2 = np.vstack(l_split_pok2)
eos_stack2 = np.vstack(l_split_eos2)

sos_stack3 = np.vstack(l_split_sos3)
pok_stack3 = np.vstack(l_split_pok3)
eos_stack3 = np.vstack(l_split_eos3)

ndvi_max_stack = np.vstack(l_ndvi_max)
# fill nearest values
sos_filled1 = fill_with_nearest_within_distance(sos_stack1, max_distance=6)  # * land_mask
pok_filled1 = fill_with_nearest_within_distance(pok_stack1, max_distance=6)  # * land_mask
eos_filled1 = fill_with_nearest_within_distance(eos_stack1, max_distance=6)  # * land_mask

sos_filled2 = fill_with_nearest_within_distance(sos_stack2, max_distance=6)  # * land_mask
pok_filled2 = fill_with_nearest_within_distance(pok_stack2, max_distance=6)  # * land_mask
eos_filled2 = fill_with_nearest_within_distance(eos_stack2, max_distance=6)  # * land_mask

sos_filled3 = fill_with_nearest_within_distance(sos_stack3, max_distance=6)  # * land_mask
pok_filled3 = fill_with_nearest_within_distance(pok_stack3, max_distance=6)  # * land_mask
eos_filled3 = fill_with_nearest_within_distance(eos_stack3, max_distance=6)  # * land_mask

sos_3d_1 = sos_filled1[np.newaxis, :, :]
pok_3d_1 = pok_filled1[np.newaxis, :, :]
eos_3d_1 = eos_filled1[np.newaxis, :, :]

sos_3d_2 = sos_filled2[np.newaxis, :, :]
pok_3d_2 = pok_filled2[np.newaxis, :, :]
eos_3d_2 = eos_filled2[np.newaxis, :, :]

sos_3d_3 = sos_filled3[np.newaxis, :, :]
pok_3d_3 = pok_filled3[np.newaxis, :, :]
eos_3d_3 = eos_filled3[np.newaxis, :, :]

export_to_cog(sos_filled1, target_transform, target_crs,
              os.path.join(path_export, f'sos_lsp_world_s1_{year}_{product_version}.tif'))
export_to_cog(eos_filled1, target_transform, target_crs,
              os.path.join(path_export, f'eos_lsp_world_s1_{year}_{product_version}.tif'))
export_to_cog(pok_filled1, target_transform, target_crs,
              os.path.join(path_export, f'pok_lsp_world_s1_{year}_{product_version}.tif'))

export_to_cog(sos_filled2, target_transform, target_crs,
              os.path.join(path_export, f'sos_lsp_world_s2_{year}_{product_version}.tif'))
export_to_cog(eos_filled2, target_transform, target_crs,
              os.path.join(path_export, f'eos_lsp_world_s2_{year}_{product_version}.tif'))
export_to_cog(pok_filled2, target_transform, target_crs,
              os.path.join(path_export, f'pok_lsp_world_s2_{year}_{product_version}.tif'))

export_to_cog(sos_filled3, target_transform, target_crs,
              os.path.join(path_export, f'sos_lsp_world_s3_{year}_{product_version}.tif'))
export_to_cog(eos_filled3, target_transform, target_crs,
              os.path.join(path_export, f'eos_lsp_world_s3_{year}_{product_version}.tif'))
export_to_cog(pok_filled3, target_transform, target_crs,
              os.path.join(path_export, f'pok_lsp_world_s3_{year}_{product_version}.tif'))

export_to_cog(ndvi_max_stack, target_transform, target_crs,
              os.path.join(path_export, f'ndvimax_world_{year}_{product_version}.tif'))
