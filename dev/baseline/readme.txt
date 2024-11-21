Attributes:

1. fid, indekso: These are organizing indexes. They should not be included into the model features.
2. SOS, EOS: Start and End of Season. They are inputed to the model as the 'target' variable.
3. lat, lon: Geometric variables to generate the geometry. Not used for the model (although they could be).
4. temperature_****: Temperature features from AgERA5 at 0.5º at the equator from 1979 to 2020. 
5. dewpoint_****: Dewpoint temperature features from AgERA5 at 0.5º at the equator from 1979 to 2020. 
6. precipitation_****: Precipitation features from AgERA5 at 0.5º at the equator from 1979 to 2020. 
7. aspect, height, slope: Aspect, Height and Slope for each pixel of the World.
8. Legacy: 1 if they come from the pre-expansion using the WorldCereal Active Croplands Masks.
9. Source: 'Phase I' if they come from the Phase I Baseline (although it was latter modified to include more countries, the pre-dormancy stage and some fixes were applied). 'Visual inspect' if they come from the Visual interpretation of the LSP-Google Earth Engine tool results. 'End user' if they come from additions or corrections form end users feedback.
