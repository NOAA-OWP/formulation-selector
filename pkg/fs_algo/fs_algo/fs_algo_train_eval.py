from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_squared_error, r2_score
import pandas as pd
import xarray as xr
import pynhd as nhd
import dask_expr
import dask.dataframe as dd
import os
from collections.abc import Iterable
from typing import List, Optional, Dict
from pathlib import Path
import joblib

# %% ATTRIBUTES
def fs_read_attr_comid(dir_db_attrs:str | os.PathLike, comids_resp:list, attrs_sel = 'all',
                       _s3 = None,storage_options=None)-> dask_expr._collection.DataFrame:
    if _s3:
        storage_options={"anon",True} # for public
    
    # Read attribute data acquired using fsds.attr.hydfab R package
    all_attr_df = dd.read_parquet(dir_db_attrs, storage_options = storage_options)

    # Subset based on comids of interest
    attr_df_subloc = all_attr_df[all_attr_df['featureID'].str.contains('|'.join(comids_resp))]

    if attrs_sel == 'all':
        # TODO shold figure out which attributes are common across all data when using 'all'
        attrs_sel = attr_df_subloc['attribute'].unique().compute()

    attr_df_sub = attr_df_subloc[attr_df_subloc['attribute'].str.contains('|'.join(attrs_sel))]
    return attr_df_sub

def _find_feat_srce_id(dat_resp: Optional[xr.core.dataset.Dataset] = None,
                       config: Optional[Dict] = None) -> List[str]:
    # Attempt to grab dataset attributes (in cases where it differs by dataset), fallback on config file
    featureSource = None
    try: # dataset attributes first
        featureSource = dat_resp.attrs.get('featureSource', None)
    except (KeyError, StopIteration): # config file second
        featureSource = next(x['featureSource'] for x in config['col_schema'] if 'featureSource' in x)
    if not featureSource:
        raise ValueError(f'The featureSource could not be found. Ensure it is present in the col_schema section {path_config}')
    # Attempt to grab featureID from dataset attributes, fallback to the config file
    featureID = None
    try: # dataset attributes first
        featureID = dat_resp.attrs.get('featureID', None)
    except (KeyError, StopIteration): # config file second
        featureID = next(x['featureID'] for x in config['col_schema'] if 'featureID' in x)
    if not featureID:
        raise ValueError(f'The featureID could not be found. Ensure it is present in the col_schema section of {path_config}')
        # TODO need to map gage_id to location identifier in attribute data!

    return [featureSource, featureID]

def fs_retr_nhdp_comids(featureSource:str,featureID:str,gage_ids: Iterable[str] ) ->list:
    # Retrieve response variable's comids, querying the shortest distance in the flowline
    nldi = nhd.NLDI()
    comids_resp = [nldi.navigate_byid(fsource=featureSource,fid= featureID.format(gage_id=gage_id),
                                navigation='upstreamMain',
                                source='flowlines',
                                distance=1).loc[0]['nhdplus_comid'] 
                                for gage_id in gage_ids]
    return comids_resp

# %% ALGORITHM TRAINING AND EVALUATION
class AlgoTrainEval:
    def __init__(self, df: pd.DataFrame, vars: Iterable[str], algo_config: dict,
                 dir_out_alg_ds: str | os.PathLike, dataset_id: str,
                 metr: str = None, test_size: float = 0.7,rs: int = 32):
        # class args
        self.df = df
        self.vars = vars
        self.algo_config = algo_config
        self.dir_out_alg_ds = dir_out_alg_ds
        self.metric = metr
        self.test_size = test_size
        self.rs = rs
        self.dataset_id = dataset_id

        # train/test split
        self.X_train = pd.DataFrame()
        self.X_test = pd.DataFrame()
        self.y_train = pd.Series()
        self.y_test = pd.Series()
        
        # train/pred/eval metadata
        self.algs_dict = {}
        self.preds_dict = {}
        self.eval_dict = {}

        # The evaluation summary result
        self.eval_df = pd.DataFrame()
    def split_data(self):
        X = self.df[self.vars]
        y = self.df[self.metric]
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(X,y, test_size=self.test_size, random_state=self.rs)
        

    def train_algos(self):

        # Train algorithms based on config
        if 'rf' in self.algo_config:  # RANDOM FOREST
            rf = RandomForestRegressor(n_estimators=self.algo_config['rf'].get('n_estimators'),
                                       random_state=self.rs)
            rf.fit(self.X_train, self.y_train)
            self.algs_dict['rf'] = {'algo': rf,
                                    'type': 'random forest regressor',
                                    'metric': self.metric}

        if 'mlp' in self.algo_config:  # MULTI-LAYER PERCEPTRON
            mlpcfg = self.algo_config['mlp']
            mlp = MLPRegressor(random_state=self.rs,
                               hidden_layer_sizes=mlpcfg.get('hidden_layer_sizes', (100,)),
                               activation=mlpcfg.get('activation', 'relu'),
                               solver=mlpcfg.get('solver', 'lbfgs'),
                               alpha=mlpcfg.get('alpha', 0.001),
                               batch_size=mlpcfg.get('batch_size', 'auto'),
                               learning_rate=mlpcfg.get('learning_rate', 'constant'),
                               power_t=mlpcfg.get('power_t', 0.5),
                               max_iter=mlpcfg.get('max_iter', 200))
            mlp.fit(self.X_train, self.y_train)
            self.algs_dict['mlp'] = {'algo': mlp,
                                     'type': 'multi-layer perceptron regressor',
                                     'metric': self.metric}

    def predict_algos(self):
        # Make predictions with trained algorithms
        
        for k, v in self.algs_dict.items():
            algo = v['algo']
            y_pred = algo.predict(self.X_test)
            self.preds_dict[k] = {'y_pred': y_pred,
                             'type': v['type'],
                             'metric': v['metric']}
        return self.preds_dict

    def evaluate_algos(self):
        # Evaluate the predictions
        # TODO add more evaluation metrics here
        for k, v in self.preds_dict.items():
            y_pred = v['y_pred']
            self.eval_dict[k] = {'type': v['type'],
                            'metric': v['metric'],
                            'mse': mean_squared_error(self.y_test, y_pred),
                            'r2': r2_score(self.y_test, y_pred)}
        return self.eval_dict

    def save_algos(self):
        # Write algorithm to file & record save path in algs_dict['loc_algo']
        for algo in self.algs_dict.keys():
            print(f"      Saving {algo} for {self.metric} to file")

            basename_alg_ds_metr = f'algo_{algo}_{self.metric}__{self.dataset_id}'
            path_algo = Path(self.dir_out_alg_ds) / Path(basename_alg_ds_metr + '.joblib')
            # write trained algorithm
            joblib.dump(self.algs_dict[algo]['algo'], path_algo)
            self.algs_dict[algo]['loc_algo'] = path_algo
   
    def org_metadata_alg(self):
        # Must be called after running AlgoTrainEval.save_algos()
        # Record location of trained algorithm
        self.eval_df = pd.DataFrame(self.eval_dict).transpose().rename_axis(index='algorithm')
        # Assign the locations where algorithms were saved
        self.eval_df['loc_algo'] = [self.algs_dict[alg]['loc_algo'] for alg in self.algs_dict.keys()] 
    
    
    def train_eval(self):
        # Overall train, test, evaluation wrapper

        # Run the train/test split
        self.split_data()

        # Train algorithms # returns self.algs_dict 
        self.train_algos()

        # Make predictions  # 
        self.predict_algos()

        # Evaluate predictions # returns self.eval_dict
        self.evaluate_algos()

        # Write algorithms to file # returns self.algs_dict_paths
        self.save_algos()

        # Generate metadata dataframe
        self.org_metadata_alg() # Must be called after trainer.save_algos()
        
# %%