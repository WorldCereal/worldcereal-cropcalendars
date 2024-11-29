import os
import numpy as np
import rasterio
import scipy.ndimage as scimg

pre_path  = '/media/nas3/Andreu/'

def toCircular(values, maxvalue = 365, rad = True):
    circvalue = (values*360)/maxvalue
    if rad:
        circvalue = np.deg2rad(circvalue)

    return np.array(circvalue)

def fromCircular(circvalues, maxvalue = 365, rad = True):
    if rad:
        circvalues = np.rad2deg(circvalues)
    value = (circvalues*maxvalue)/360
    return value

def circularMean(circ_data, scal_max = 365, narm = True, rad=False, percentile = None, verbose=True):
    import math

    if verbose:
        print("USE IT ON DOYS ONLY (without pass them to radians)")
    if rad: tocirc = circ_data
    else:
        tocirc = toCircular(circ_data, maxvalue=scal_max)
    if narm: tocirc = tocirc[~np.isnan(tocirc)]

    if np.sum(tocirc) == 0:
        return 0

    if percentile is not None:
        pTop = np.percentile(tocirc, percentile)
        pBot = np.percentile(tocirc, 100-percentile)
        tocirc = tocirc[(tocirc <= pTop) & (tocirc >= pBot)]

    # is it radians? Let's suppose that not
    x_mean = np.cos(tocirc).mean()
    y_mean = np.sin(tocirc).mean()

    r_mean = np.sqrt(x_mean**2 + y_mean**2)

    x = x_mean/r_mean
    y = y_mean/r_mean

    arctan = np.abs(np.arctan2(y,x))
    if y > 0 and x > 0:
        theta_mean = arctan
    if y > 0 and x < 0:
        theta_mean = np.pi-arctan
    if y < 0 and x < 0:
        theta_mean = np.pi+arctan
    if y < 0 and x > 0:
        theta_mean = 2*np.pi-arctan

    # back to doys
    if rad:
        back_scalar = theta_mean
    else:
        back_scalar = fromCircular(theta_mean, maxvalue=scal_max)
    return back_scalar


if __name__ == "__main__":

    path_wc_sos_filled = pre_path + '/post_processing/filling_gaps/wc_sos_los_filled.tif'
    path_wc_eos_filled = pre_path + '/post_processing/filling_gaps/wc_eos_los_filled.tif'
    path_sc_sos_filled = pre_path + '/post_processing/filling_gaps/sc_sos_los_filled.tif'
    path_sc_eos_filled = pre_path + '/post_processing/filling_gaps/sc_eos_los_filled.tif'

    path_wc_sos_3x3 = pre_path + '/post_processing/moving_window/wc_sos_los_3x3.tif'
    path_wc_eos_3x3 = pre_path + '/post_processing/moving_window/wc_eos_los_3x3.tif'
    path_sc_sos_3x3 = pre_path + '/post_processing/moving_window/sc_sos_los_3x3.tif'
    path_sc_eos_3x3 = pre_path + '/post_processing/moving_window/sc_eos_los_3x3.tif'

    # Read files with filled borders
    with rasterio.open(path_wc_sos_filled) as src:
        data1 = src.read(1)
        profile = src.profile
    with rasterio.open(path_wc_eos_filled) as src:
        data2 = src.read(1)
    with rasterio.open(path_sc_sos_filled) as src:
        data3 = src.read(1)
    with rasterio.open(path_sc_eos_filled) as src:
        data4 = src.read(1)

    data1 = data1.astype(np.float32)
    data1[data1 == 0] = np.nan
    data2 = data2.astype(np.float32)
    data2[data2 == 0] = np.nan
    data3 = data3.astype(np.float32)
    data3[data3 == 0] = np.nan
    data4 = data4.astype(np.float32)
    data4[data4 == 0] = np.nan

    # Define filter
    w = np.ones((3,3))
    # Apply 3x3 filter
    data1_3x3 = scimg.generic_filter(data1, circularMean, footprint=w)
    data2_3x3 = scimg.generic_filter(data2, circularMean, footprint=w)
    data3_3x3 = scimg.generic_filter(data3, circularMean, footprint=w)
    data4_3x3 = scimg.generic_filter(data4, circularMean, footprint=w)

    # WC SOS
    data1_3x3[(data1_3x3 > 0) & (data1_3x3 < 1)] = 1
    data1_3x3[np.isnan(data1_3x3)] = 0
    data1_3x3 = data1_3x3.astype(np.int16)
    # WC EOS
    data2_3x3[(data2_3x3 > 0) & (data2_3x3 < 1)] = 1
    data2_3x3[np.isnan(data2_3x3)] = 0
    data2_3x3 = data2_3x3.astype(np.int16)
    # SC SOS
    data3_3x3[(data3_3x3 > 0) & (data3_3x3 < 1)] = 1
    data3_3x3[np.isnan(data3_3x3)] = 0
    data3_3x3 = data3_3x3.astype(np.int16)
    # SC EOS
    data4_3x3[(data4_3x3 > 0) & (data4_3x3 < 1)] = 1
    data4_3x3[np.isnan(data4_3x3)] = 0
    data4_3x3 = data4_3x3.astype(np.int16)

    # Write the smoothed calendars
    with rasterio.open(path_wc_sos_3x3, 'w', **profile) as dst:
        dst.write(data1_3x3, 1)
    with rasterio.open(path_wc_eos_3x3, 'w', **profile) as dst:
        dst.write(data2_3x3, 1)
    with rasterio.open(path_sc_sos_3x3, 'w', **profile) as dst:
        dst.write(data3_3x3, 1)
    with rasterio.open(path_sc_eos_3x3, 'w', **profile) as dst:
        dst.write(data4_3x3, 1)


