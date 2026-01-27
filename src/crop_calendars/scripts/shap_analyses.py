import os
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
import matplotlib.pyplot as plt
import shap
from time import perf_counter

models_path = '/path/to/models'
seos = ['sc_sos', 'sc_eos', 'wc_sos', 'wc_eos']
seasons = {
    "wc_sos": "s1_sos",
    "wc_eos": "s1_eos",
    "sc_sos": "s2_sos",
    "sc_eos": "s2_eos"
}
seasons2 = {
    "wc_sos": "Winter Crops SOS",
    "wc_eos": "Winter Crops EOS",
    "sc_sos": "Summer Crops SOS",
    "sc_eos": "Summer Crops EOS"
}
points_path = '/path/to/points'
# points_agera5_world_minus_oceans.csv is the same file as AgERA5 from necessary folder but without the points
# corresponding to the ocean
points = pd.read_csv(os.path.join(points_path, 'points_agera5_world_minus_oceans.csv'))

for season in seos:
    print(f'Starting with {season}')
    sin_model_path = os.path.join(models_path, f'{seasons[season]}_xgboost_sin_model.json')
    cos_model_path = os.path.join(models_path, f'{seasons[season]}_xgboost_cos_model.json')
    results_path = '/path/to/outputs'
    sin_features_path = os.path.join(results_path, season, 'top_feature_sin.csv')
    cos_features_path = os.path.join(results_path, season, 'top_feature_cos.csv')

    output_path = '/path/to/output_shap'

    sin_predictors = pd.read_csv(sin_features_path)
    cos_predictors = pd.read_csv(cos_features_path)
    sin_predictors = sin_predictors['Top sin features']
    cos_predictors = cos_predictors['Top cos features']

    sin_xgboost_model = XGBRegressor()
    cos_xgboost_model = XGBRegressor()
    sin_xgboost_model.load_model(sin_model_path)
    cos_xgboost_model.load_model(cos_model_path)
    print('Models loaded, calculating things')
    # A id must be chosen
    inici = perf_counter()
    # Predictors
    full_sin = points[sin_predictors]
    full_cos = points[cos_predictors]
    # full
    explainer = shap.TreeExplainer(sin_xgboost_model)
    shap_values = explainer(full_sin)
    plt.figure()
    shap.summary_plot(shap_values, full_sin, show=False)
    plt.title(f'{seasons2[season]} Sin SHAP')
    plt.savefig(os.path.join(output_path, f'{season}_sin_shap.png'), dpi=300)

    explainer = shap.TreeExplainer(cos_xgboost_model)
    shap_values = explainer(full_cos)
    plt.figure()
    fig = shap.summary_plot(shap_values, full_cos, show=False)
    plt.title(f'{seasons2[season]} Cos SHAP')
    plt.savefig(os.path.join(output_path, f'{season}_cos_shap.png'), dpi=300)

    plt.close('all')
    final = perf_counter()
    print(f'{season} took {final-inici} seconds to be processed')








