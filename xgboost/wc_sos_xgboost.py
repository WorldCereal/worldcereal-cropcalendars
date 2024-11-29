import os
import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from xgboost import XGBRegressor
from shapely.geometry import Point
import matplotlib.pyplot as plt
import seaborn as sns
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from affine import Affine

os.chdir('/media/nas3/Andreu/WC_CropCalendars')

'''Paths'''
file_path = '/expanded_datasets/winter_expanded_.csv'
results_path = '/prod/outputs/wc_sos'
necessary_path = '/prod/inputs/necessary'
y_pred_path = results_path + '/y_pred.csv'
y_test_path = results_path + '/y_test.csv'
problems_path = results_path + '/wc_sos_problems.csv'
sin_features_path = results_path + '/top_feature_sin.csv'
cos_features_path = results_path + '/top_feature_cos.csv'
data_world = necessary_path + '/AgERA5.csv'
rmaskpath = necessary_path + '/ultramonasap_winterwheat_toMaxmask_50km_3857.tif'
mask_template_path = necessary_path + '/worldmask_50km_3857.tif'
mask_path = necessary_path + '/CropCoverFraction_50km_3857.tif'
template_path = necessary_path + '/tftest50km_v9.tif'
gdf_file = necessary_path + '/ne_10m_admin_0_sovereignty/ne_10m_admin_0_sovereignty.shp'
continents_gdf = gpd.read_file(gdf_file)


'''Parameters for the XGBoost model'''
params_sin = {
    'n_estimators': 1000,  # Number of boosting rounds
    'max_depth': 15,                  # Maximum depth of a tree
    'learning_rate': 0.1,             # Step size shrinkage used to prevent overfitting
    'subsample': 0.8,                 # Subsample ratio of the training instances
    'colsample_bytree': 0.8,          # Subsample ratio of columns when constructing each tree
    'random_state': 542,              # Random seed for reproducibility
    'objective': 'reg:squarederror'   # Specify objective for regression tasks
}

params_cos = {
    'n_estimators': 1000,  # Number of boosting rounds
    'max_depth': 15,                  # Maximum depth of a tree
    'learning_rate': 0.1,             # Step size shrinkage used to prevent overfitting
    'subsample': 0.8,                 # Subsample ratio of the training instances
    'colsample_bytree': 0.8,          # Subsample ratio of columns when constructing each tree
    'random_state': 542,              # Random seed for reproducibility
    'objective': 'reg:squarederror'   # Specify objective for regression tasks
}


'''Proper script'''
data = pd.read_csv(file_path)
data.drop(columns='EOS',inplace=True)
data = data.rename(columns={'SOS':'target'})
# Solving some issues
data = data.dropna()
# Transforming DOYs to circular
data['target'] = data['target']*360/365
data['target'] = np.deg2rad(data['target'])
# Define the predictors (features for training the model)
predictors = data.columns.drop({'algo', 'fid', 'indekso', 'target', 'x', 'y', 'Legacy', 'layer', 'path'})
# Define sin/cos datasets to predict
sin_pred = data.copy()
cos_pred = data.copy()
sin_pred['target'] = np.sin(sin_pred['target'])
cos_pred['target'] = np.cos(cos_pred['target'])

'''Weighting the points'''
sample_weight = np.ones(len(data))
sample_weight[data['Source']=='Phase I'] = 1
sample_weight[data['Source']=='End user'] = 4
sample_weight[data['Source']=='Visual inspect'] = 0.5
# sample_weight = np.random.rand(len(data))
# Removing unncessary features
predictors = predictors.drop({'Source'})


'''Necessary for later'''
X = data[predictors]
y = data['target']
X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(X, y, sample_weight, test_size=0.30, random_state=542)
cosa = X_test.copy()
y_test_2 = y_test.copy()
'''End necessary for later'''

'''Feature selection. Comment and uncomment to select different variables'''
number = 50 # number of top features
# predictors = [i for i in predictors if "whole" not in i]
# predictors = [i for i in predictors if "Max" not in i]
# predictors = [i for i in predictors if "Min" not in i]
# predictors = [i for i in predictors if "Amplitude" not in i]
# predictors = [i for i in predictors if "Month" not in i]
predictors = [i for i in predictors if "dist" not in i]
predictors = [i for i in predictors if "lat" not in i]
predictors = [i for i in predictors if "lon" not in i]
# predictors = [i for i in predictors if "aspect" not in i]
# predictors = [i for i in predictors if "slope" not in i]
# predictors = [i for i in predictors if "Std" not in i]
# predictors = [i for i in predictors if "Mean" not in i]
# predictors = [i for i in predictors if "height" not in i]
predictors = [i for i in predictors if not ("temperature" in i and "Total" in i)]
predictors = [i for i in predictors if not ("dewpoint" in i and "Total" in i)]


'''SIN'''
X = sin_pred[predictors]
y = sin_pred['target']

# Split the data into training and testing sets
X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(X, y, sample_weight, test_size=0.30, random_state=542)
# Define the xgboost regressor
sin_random_xgboost_model = XGBRegressor(**params_sin)
# Fit the model
sin_random_xgboost_model.fit(X_train, y_train, sample_weight=w_train)

# Getting important features
feature_importances = sin_random_xgboost_model.feature_importances_
sorted_indices = np.argsort(feature_importances)[::-1]
num_top_features = number  # specify the number of top features you want
top_features_sin = [predictors[i] for i in sorted_indices[:num_top_features]]

# Retrieve top features of sin
thingy = pd.DataFrame({'Features':predictors, 'Feature importance': feature_importances})
thing = pd.DataFrame({'Top sin features': top_features_sin, 'Top sin feature importance': feature_importances[sorted_indices[:num_top_features]]})
thing.to_csv(sin_features_path)

sin_xgboost_model = XGBRegressor(**params_sin)

# Fit the model
sin_xgboost_model.fit(X_train[top_features_sin], y_train, sample_weight=w_train)
score_sin = sin_xgboost_model.score(X_test[top_features_sin], y_test)
y_pred_sin = sin_xgboost_model.predict(X_test[top_features_sin])



'''COS'''
X = cos_pred[predictors]
y = cos_pred['target']

# Split the data into training and testing sets
X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(X, y, sample_weight, test_size=0.30, random_state=542)
# Initialize and train the XGBoost model
cos_random_xgboost_model = XGBRegressor(**params_cos)
# Fit the model
cos_random_xgboost_model.fit(X_train, y_train, sample_weight=w_train)

# Getting importances
feature_importances = cos_random_xgboost_model.feature_importances_
sorted_indices = np.argsort(feature_importances)[::-1]
num_top_features = number  # specify the number of top features you want
top_features_cos = [predictors[i] for i in sorted_indices[:num_top_features]]

thing2 = pd.DataFrame({'Top cos features': top_features_cos, 'Top cos feature importance': feature_importances[sorted_indices[:num_top_features]]})
thing2.to_csv(cos_features_path)

cos_xgboost_model = XGBRegressor(**params_cos)
cos_xgboost_model.fit(X_train[top_features_cos], y_train, sample_weight=w_train)
score_cos = cos_xgboost_model.score(X_test[top_features_cos], y_test)
y_pred_cos = cos_xgboost_model.predict(X_test[top_features_cos])


# Transforming sin/cos model into DOY data
y_pred = np.arctan2(y_pred_sin,y_pred_cos)
y_test = y_test_2.copy()
y_pred = np.rad2deg(y_pred)*365/360
y_test = np.rad2deg(y_test)*365/360


# FINAL REGRESSION
import statsmodels.api as sm
ytest2 = y_test.copy()
pred2 = y_pred.copy()
pred2 = pd.Series(pred2)
pred2[pred2 < 0] += 365
pred2[pred2 < 1] += 1
np.savetxt(y_pred_path, pred2, delimiter=',')
np.savetxt(y_test_path, y_test, delimiter=',')

pred2 = pred2.to_numpy()
predit = pred2.copy()
pred2 = pd.DataFrame(pred2)
ytest2 = ytest2.to_numpy()
observat = ytest2.copy()
ytest2 = pd.DataFrame(ytest2)
predit = pd.DataFrame({'Predit':predit})
observat = pd.DataFrame({'Observat':observat})


'''To check problematic points'''
aa=cosa['lat'].to_numpy()
bb=cosa['lon'].to_numpy()
problema = pd.DataFrame({'lat':aa,'lon':bb})
problems = pd.concat([problema,observat,predit],axis=1)
problems['diff'] = np.absolute(problems['Observat']-problems['Predit'])
problems = problems[(problems['diff']>25)&(problems['diff']<335)]
problems.to_csv(problems_path)
'''End to check problematic points'''

"""For all, uncomment these lines"""
#pred2[(ytest2<100)&(pred2>300)] -= 365
#pred2[(ytest2>300)&(pred2<50)] += 365


pred2 = pred2.to_numpy()
ytest2 = ytest2.to_numpy()
#############################################################################################
lat = cosa['lat'].to_numpy()
lon = cosa['lon'].to_numpy()
lat = pd.DataFrame({'lat':lat})
lon = pd.DataFrame({'lon':lon})
pred3 = np.ravel(pred2)
predit = pd.DataFrame({'Predit':pred3})
# observat = pd.DataFrame({'Observat':ytest2})
algo = pd.concat([observat,predit,lat,lon],axis=1)
algo['geometry'] = algo.apply(lambda row: Point(row['lon'], row['lat']), axis=1)
points_gdf = gpd.GeoDataFrame(algo, geometry='geometry')
points_gdf.set_crs(epsg=4326, inplace=True)
continents_gdf = continents_gdf[['SOVEREIGNT','geometry']]
# Check CRS
if points_gdf.crs != continents_gdf.crs:
    points_gdf = points_gdf.to_crs(continents_gdf.crs)
# Joined
joined_df = gpd.sjoin(points_gdf, continents_gdf, how='left', op='within')
joined_df.drop(columns='index_right', inplace=True)
# Example DataFrame
data = joined_df[['Observat','Predit','SOVEREIGNT']]
data = data.dropna()
df = pd.DataFrame(data)
unique_z_values = df['SOVEREIGNT'].unique()
palette = sns.color_palette("tab10", len(unique_z_values))
color_map = dict(zip(unique_z_values, palette))
#############################################################################################
variables = sm.add_constant(ytest2)
lm = sm.OLS(pred2, variables)
res=lm.fit()

rmse = np.sqrt(mean_squared_error(ytest2, pred2))
bias = np.mean(pred2 - ytest2)
std = np.std(pred2 - ytest2)
std = np.round(std, 2)
std = np.round(std, 2)
slope = res.params[1]*ytest2 + res.params[0]

plt.figure(figsize=(6, 6))
for z_value in unique_z_values:
    subset = df[df['SOVEREIGNT'] == z_value]
    plt.scatter(subset['Observat'], subset['Predit'], color=color_map[z_value], edgecolor='black', label=z_value)
plt.plot(ytest2, slope, color="red")
plt.text(x=15, y=305, s=f"R²={np.round(res.rsquared, 2)}")
plt.text(x=85, y=305, s=f"RMSE={np.round(rmse,2)}")
plt.text(x=15, y=285, s=f"Bias={np.round(bias,2)}")
plt.text(x=85, y=285, s=f"Std={np.round(std,2)}")
plt.xlim(0, 366)
plt.ylim(0, 366)
plt.xlabel("Predicted (DOY)")
plt.ylabel("Observed (DOY)")
plt.title("Winter crops SOS validation")
handles, labels = plt.gca().get_legend_handles_labels()
desired_order = ['Africa', 'North America', 'South America', 'Central America', 'Asia', 'Europe', 'Oceania']
# desired_order = ['Africa', 'North America', 'South America', 'Asia', 'Europe', 'Oceania']
sorted_handles_labels = sorted(zip(handles, labels), key=lambda x: desired_order.index(x[1]))
sorted_handles, sorted_labels = zip(*sorted_handles_labels)
plt.legend(sorted_handles, sorted_labels, title="Continent", loc='lower right')
plt.savefig(os.path.join(results_path, "r2validation-s1-sos.png"))


# GETTING FEATURES OF THE WHOLE PLANET
data_world = pd.read_csv(data_world)
# Removing the oceans
data_world = data_world.fillna(-9999)
# Removing unnecessary columns
data_world.drop(columns={'indekso', 'target', 'x', 'y'},inplace=True)
# Predicting for the whole world
data_world_sin = data_world[top_features_sin]
data_world_cos = data_world[top_features_cos]
world_predict_sin = sin_xgboost_model.predict(data_world_sin)
world_predict_cos = cos_xgboost_model.predict(data_world_cos)
world_predict = np.rad2deg(np.arctan2(world_predict_sin,world_predict_cos))*365/360
world_predict[world_predict < 0] += 365
world_predict[world_predict > 365] -= 365


'''Creating the maps'''
with rasterio.open(rmaskpath) as src:
    rmask = src.read(1)

with rasterio.open(mask_template_path) as worldmaskds:
    worldmask = worldmaskds.read(1)
    worldmask[worldmask < 0] = 0

finalimg = np.reshape(world_predict, (1, rmask.shape[0], rmask.shape[1]))[0]

with rasterio.open(mask_path) as mask_ds:
    mask = mask_ds.read(1)
    mask[mask == 0] = np.nan
    mask[~np.isnan(mask)] = 1

finalimgmasked = finalimg * mask
finalimgworldmasked = finalimg * worldmask

finalimg[finalimg==finalimg[0,0]] = 0
finalimg[(finalimg > 0)&(finalimg<1)] = 1
finalimgmasked[(finalimgmasked > 0)&(finalimgmasked<1)] = 1
finalimgmasked[np.isnan(finalimgmasked)] = 0
finalimgworldmasked[(finalimgworldmasked > 0)&(finalimgworldmasked<1)] = 1

finalimg = finalimg.astype(np.int16)
finalimgmasked = finalimgmasked.astype(np.int16)
finalimgworldmasked = finalimgworldmasked.astype(np.int16)

# Save results
target_crs = 'EPSG:4326'
with rasterio.open(template_path) as template:
    profile = template.profile
    resolution = 0.5  # 0.5 degrees per pixel
    transform = Affine(resolution, 0, -180,  # Origin x-coordinate
                           0, -resolution, 90)     # Origin y-coordinate
    min_lon, max_lon = -180, 180
    min_lat, max_lat = -90, 90
    width = int((max_lon - min_lon) / resolution)
    height = int((max_lat - min_lat) / resolution)
    profile.update({
        'crs': target_crs,
        'transform': transform,
        'width': width,
        'height': height,
        'dtype': np.int16,
        'nodata': 0
    })
    # profile.update(dtype=np.int16, nodata=0)
    with rasterio.open(os.path.join(results_path, "s1_sos_50km.tif"), "w", **profile) as dst:
        reproject(
            source=finalimg,  # Read the first (and only) band
            destination=rasterio.band(dst, 1),  # Write to the same band in the output
            src_transform=template.transform,
            src_crs=template.crs,
            dst_transform=transform,
            dst_crs=target_crs,
            resampling=Resampling.nearest  # Use 'nearest' for categorical data
        )
    with rasterio.open(os.path.join(results_path, "s1_sos_masked.tif"), "w", **profile) as dst:
        reproject(
            source=finalimgmasked,  # Read the first (and only) band
            destination=rasterio.band(dst, 1),  # Write to the same band in the output
            src_transform=template.transform,
            src_crs=template.crs,
            dst_transform=transform,
            dst_crs=target_crs,
            resampling=Resampling.nearest  # Use 'nearest' for categorical data
        )
    with rasterio.open(os.path.join(results_path, "s1_sos_worldmasked.tif"), "w", **profile) as dst:
        reproject(
            source=finalimgworldmasked,  # Read the first (and only) band
            destination=rasterio.band(dst, 1),  # Write to the same band in the output
            src_transform=template.transform,
            src_crs=template.crs,
            dst_transform=transform,
            dst_crs=target_crs,
            resampling=Resampling.nearest  # Use 'nearest' for categorical data
        )
