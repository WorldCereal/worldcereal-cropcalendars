import os
import numpy as np
import pandas as pd
import rasterio

os.chdir('/media/nas3/Andreu/WC_CropCalendars')

path = '/prod/outputs/wc_sos/wc_sos_50km.tif'
path2 = '/prod/outputs/wc_eos/wc_eos_50km.tif'
path3 = '/prod/outputs/sc_sos/sc_sos_50km.tif'
path4 = '/prod/outputs/sc_eos/sc_eos_50km.tif'

los_path_wc = '/post_processing/length_of_season_check/los_wc.tif'
los_path_sc = '/post_processing/length_of_season_check/los_sc.tif'
mask_los_path_wc = '/post_processing/length_of_season_check/mask_los_wc.tif'
mask_los_path_sc = '/post_processing/length_of_season_check/mask_los_sc.tif'

path_wc_sos_corrected = '/post_processing/length_of_season_check/wc_sos_los_corrected.tif'
path_wc_eos_corrected = '/post_processing/length_of_season_check/wc_eos_los_corrected.tif'
path_sc_sos_corrected = '/post_processing/length_of_season_check/sc_sos_los_corrected.tif'
path_sc_eos_corrected = '/post_processing/length_of_season_check/sc_eos_los_corrected.tif'

# Decide if you want to generate a new series of crop calendars with cleaned LOS or not
# The next steps of post-processing assume destroy = True but manual post-processing on this stage can be done
destroy = True

# Opening files of SOS and EOS for each season
with rasterio.open(path) as src:
    data1 = src.read(1)
    profile = src.profile
with rasterio.open(path2) as src:
    data2 = src.read(1)
with rasterio.open(path3) as src:
    data3 = src.read(1)
with rasterio.open(path4) as src:
    data4 = src.read(1)

# Calculating length of season
los_wc = data2 - data1
los_wc[los_wc < 0] += 365
los_wc[los_wc > 365] -= 365
los_sc = data4 - data3
los_sc[los_sc < 0] += 365
los_sc[los_sc > 365] -= 365

# Writing this files
with rasterio.open(los_path_wc, 'w', **profile) as dst:
    dst.write(los_wc, 1)
with rasterio.open(los_path_wc, 'w', **profile) as dst:
    dst.write(los_wc, 1)

# Checking for length of season problems
# 1 for problems, 0 for correct length
mask_los_wc = np.zeros([los_wc.shape[0], los_wc.shape[1]])
mask_los_wc[los_wc < 75] = 1
mask_los_wc[los_wc > 300] = 1
mask_los_sc = np.zeros([los_sc.shape[0], los_sc.shape[1]])
mask_los_sc[los_sc < 75] = 1
mask_los_sc[los_sc > 300] = 1

# Write the masks
with rasterio.open(mask_los_path_wc, 'w', **profile) as dst:
    dst.write(los_wc, 1)
with rasterio.open(mask_los_path_wc, 'w', **profile) as dst:
    dst.write(los_wc, 1)

# Delete points with strange length of season
if destroy:
    data1[mask_los_wc == 1] = 0
    data2[mask_los_wc == 1] = 0
    data3[mask_los_sc == 1] = 0
    data4[mask_los_sc == 1] = 0
    with rasterio.open(path_wc_sos_corrected, 'w', **profile) as dst:
        dst.write(data1, 1)
    with rasterio.open(path_wc_eos_corrected, 'w', **profile) as dst:
        dst.write(data2, 2)
    with rasterio.open(path_sc_sos_corrected, 'w', **profile) as dst:
        dst.write(data3, 1)
    with rasterio.open(path_sc_eos_corrected, 'w', **profile) as dst:
        dst.write(data4, 2)



