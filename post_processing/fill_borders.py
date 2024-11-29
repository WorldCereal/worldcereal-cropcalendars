import os
import numpy as np
import rasterio
from scipy.spatial import KDTree

pre_path = '/media/nas3/Andreu/'

def fill_with_nearest_within_distance(arr, max_distance=6):
    # Get the 2D indices of the non-NaN values
    non_nan_coords = np.array(np.where(~np.isnan(arr))).T
    # Get the 2D indices of the NaN values
    nan_coords = np.array(np.where(np.isnan(arr))).T
    # Create a KDTree from the non-NaN positions
    tree = KDTree(non_nan_coords)
    # For each NaN position, find the index of the nearest non-NaN value
    distances, indices = tree.query(nan_coords)
    # Only fill the NaN positions whose nearest non-NaN value is within the max_distance
    fillable_positions = np.where(distances <= max_distance)
    arr[tuple(nan_coords[fillable_positions].T)] = arr[tuple(non_nan_coords[indices[fillable_positions]].T)]

    return arr

if __name__ == "__main__":

    path_wc_sos_corrected = pre_path + '/post_processing/length_of_season_check/wc_sos_los_corrected.tif'
    path_wc_eos_corrected = pre_path + '/post_processing/length_of_season_check/wc_eos_los_corrected.tif'
    path_sc_sos_corrected = pre_path + '/post_processing/length_of_season_check/sc_sos_los_corrected.tif'
    path_sc_eos_corrected = pre_path + '/post_processing/length_of_season_check/sc_eos_los_corrected.tif'

    path_wc_sos_filled = pre_path + '/post_processing/filling_gaps/wc_sos_los_filled.tif'
    path_wc_eos_filled = pre_path + '/post_processing/filling_gaps/wc_eos_los_filled.tif'
    path_sc_sos_filled = pre_path + '/post_processing/filling_gaps/sc_sos_los_filled.tif'
    path_sc_eos_filled = pre_path + '/post_processing/filling_gaps/sc_eos_los_filled.tif'

    # Read files with length of season problematic pixels deleted
    with rasterio.open(path_wc_sos_corrected) as src:
        data1 = src.read(1)
        profile = src.profile
    with rasterio.open(path_wc_eos_corrected) as src:
        data2 = src.read(1)
    with rasterio.open(path_sc_sos_corrected) as src:
        data3 = src.read(1)
    with rasterio.open(path_sc_eos_corrected) as src:
        data4 = src.read(1)

    data1[data1==0] = np.nan
    data2[data2==0] = np.nan
    data3[data3==0] = np.nan
    data4[data4==0] = np.nan

    # Expanding borders
    data1_filled = fill_with_nearest_within_distance(data1, max_distance=3)
    data2_filled = fill_with_nearest_within_distance(data2, max_distance=3)
    data3_filled = fill_with_nearest_within_distance(data3, max_distance=3)
    data4_filled = fill_with_nearest_within_distance(data4, max_distance=3)

    with rasterio.open(path_output, 'w', **profile) as dst:
        dst.write(data1_filled, 1)
    with rasterio.open(path_output, 'w', **profile) as dst:
        dst.write(data2_filled, 1)
    with rasterio.open(path_output, 'w', **profile) as dst:
        dst.write(data3_filled, 1)
    with rasterio.open(path_output, 'w', **profile) as dst:
        dst.write(data4_filled, 1)
