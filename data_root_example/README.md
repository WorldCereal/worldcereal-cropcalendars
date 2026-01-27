# Example DATA_ROOT (local-only)

This folder mirrors the expected Zenodo dataset layout so you can test paths
without committing large files. Keep your real downloads here or point
`DATA_ROOT` to another local folder.

Populate this folder with the Zenodo archive contents. Expected files:

- auxiliar_data.zip
- NDVI_hants.zip
- summer_crops_dataset.csv
- winter_crops_dataset.csv
- S1_SOS_WGS84.tif
- S1_EOS_WGS84.tif
- S2_SOS_WGS84.tif
- S2_EOS_WGS84.tif
- Phase1_legacy_cropcalendars.zip
- doy_palette.qml

After extracting:

- auxiliar_data/ (unzipped from auxiliar_data.zip)
- NDVI_hants/ (unzipped from NDVI_hants.zip)

If you want to verify checksums, the main README lists md5 values from the Zenodo record.
