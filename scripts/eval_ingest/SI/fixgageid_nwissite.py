"""
Check each dataset's nwissite gage_id format
Correct if missing leading zeros
Write the new 'fixed' dataset
"""

import pandas as pd
from fs_proc.proc_eval_metrics import check_fix_nwissite_gageids
from pathlib import Path
home_dir = str(Path.home())
dir_base = Path(f'{home_dir}/noaa/regionalization/data/SI2022')
dict_datasets = {'CFE': {'sub_path_data': 'CFE/CFE.csv',
                         'gage_id_col':'basin_id'},
                 'LSTM': {'sub_path_data': 'LSTM/LSTM.csv',
                          'gage_id_col':'basin'},
                 'lm': {'sub_path_data': 'linear_model/linear.csv',
                        'gage_id_col':'site_id'}}

for k, v in dict_datasets.items():
    path_data = Path(dir_base/Path(v['sub_path_data']))
    gage_id_col = v['gage_id_col']
    print(path_data)
    df = pd.read_csv(path_data,dtype={gage_id_col :str})
    cmbo_df = check_fix_nwissite_gageids(df, gage_id_col = gage_id_col)
    df_diff = pd.concat([df,cmbo_df]).drop_duplicates(keep=False)
    if df_diff.shape[0] > 0:
    
        new_file_name = path_data.name.replace(path_data.suffix, '_fixed' + path_data.suffix)
        path_newfile = Path(path_data.parent/Path(new_file_name))

        print(f"Writing fixed dataset as {new_file_name}")
        cmbo_df.to_csv(path_newfile)