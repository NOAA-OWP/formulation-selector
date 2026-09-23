### RaFTS Directory Structure
2025-08-06

Running the full RaFTS workflow generates the following directory structure. Note that filename structures specified below are not necessarily precise (e.g. {various_plot_files}.png are plot files with structured names for different plots that are specified in detail here.
```
{dir_base}/ # as defined in the prep config file
├── input/ # Standardized input dataused for algorithm training & location data, aka {dir_base} in attr config file
│   ├── attributes/ # The predictor data using unique location identifiers
│   │   ├── comid_{comid}_attrs.parquet # All retrieved attributes corresponding to a specific location
│   │   ├── comid_{comid}_tfrmattr.parquet # In case custom transformations were performed on some corresponding attribute data
│   │   ├── comid_{hf_uid}_attrs.parquet
│   │   └── comid_{hf_uid}_tfrmattr.parquet
│   ├── gpkg/ # All location data mapped to unique identifiers
│   │   └── all_locs.gpkg # A single file of all locations ever retrieved for RaFTS processing
│   ├── user_data_std/ # Dataset-specific/analysis specific location & attribute data
│   │   ├── {dataset1_standardized_name}/ # aka {ds1_std_name}
│   │   │   ├── {ds1_std_name}_loc.gpkg # Location data generated as a subset of input/gpkg/all_locs.gpkg & may include both training and prediction locations
│   │   │   ├── {ds1_std_name}_training.parquet # The data used for algo training/testing
│   │   │   └── {ds1_std_name}_prediction.parquet # The predictor data used for predicting response vars
│   │   ├── {dataset2_standardized_name}/ # aka {ds2_std_name}
│   │   │   ├── {ds2_std_name}_loc.gpkg  
│   │   │   ├── {ds2_std_name}_training.parquet
│   │   │   └── {ds2_std_name}_prediction.parquet
├── output/ # Outputs generated after training ML algorithms
│   ├── trained_algorithms/ # The trained algorithms for e/ dataset & response variable
│   │   ├── {dataset1_standardized_name}/
│   │   │   ├── algo_mlp_{response_var1}_{ds1_std_name}_loc_sel.joblib
│   │   │   ├── algo_mlp_{response_var2}_{ds1_std_name}_loc_sel.joblib
│   │   │   ├── algo_rf_{response_var1}_{ds1_std_name}_loc_sel.joblib
│   │   │   └── algo_rf_{response_var2}_{ds1_std_name}_loc_sel.joblib
│   ├── analysis/ # Predicted response variable values
│   │   ├── {dataset1_standardized_name}/ # The algorithm-predicted values for a dataset/response variable
│   │   │   ├── pred_obs_{ds1_std_name}_{response_var1}.csv
│   │   │   └── pred_obs_{ds1_std_name}_{response_var2}.csv
│   ├── algorithm_predictions/ # The predicted response values for each response dataset/variable-algorithm combo
│   │   ├── {dataset1_standardized_name}/
│   │   │   ├── pred_rf_{response_var1}_{ds1_std_name}_shortname.parquet
│   │   │   └── pred_mlp_{response_var1}_{ds1_std_name}_shortname.parquet
│   │   ├── {dataset2_standardized_name}/
│   │   │   ├── pred_rf_{response_var1}_{ds1_std_name}_shortname.parquet
│   │   │   └── pred_mlp_{response_var1}_{ds1_std_name}_shortname.parquet
│   └── data_visualizations/ # Regression plots, maps, etc.
│   │   ├── {dataset1_standardized_name}/
│   │   │   └── {various_plot_files}.png
│   │   ├── {dataset2_standardized_name}/
│   │   │   └── {various_plot_files}.png
```
