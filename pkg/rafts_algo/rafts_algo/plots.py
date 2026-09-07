# plots.py
from __future__ import annotations # enables the | operator for function typehints back to python 3.7
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import pathlib
from pathlib import Path
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
import geopandas as gpd
import requests
import zipfile
from typing import Iterable
import rafts_algo.utils as raftsutil
import os
import gc

# Set up basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def plot_corr_mat(df_X: pd.DataFrame,
                title='Feature Correlation Matrix'
                ) -> matplotlib.figure.Figure:
    """Generate a plot of the correlation matrix

    :param df_X: The dataset dataframe
    :type df_X: pd.DataFrame
    :param title: Plot title, defaults to 'Feature Correlation Matrix'
    :type title: str, optional
    :return: The correlation matrix figure
    :rtype: matplotlib.figure.Figure
    """
    # Calculate the correlation matrix
    df_corr = df_X.corr()

    #  Plot the correlation matrix
    plt.figure(figsize=(10,8))
    sns.heatmap(df_corr, annot=True, cmap ='coolwarm',linewidths=0.5, fmt='.2f')
    plt.title(title)

    fig = plt.gcf()
    return fig

def std_corr_mat_plot_path(dir_out_viz_base: str | Path,
                            ds: str
                            ) -> pathlib.PosixPath:
    """Standardize the filepath for saving correlation matrix above a threshold

    :param dir_out_viz_base: The base visualization output directory
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The dataset name
    :type ds: str
    :return: The correlation matrix filepath
    :rtype: pathlib.PosixPath
    """
    path_corr_mat = Path(f"{dir_out_viz_base}/{ds}/correlation_matrix_{ds}.png")
    path_corr_mat.parent.mkdir(parents=True,exist_ok=True)
    return path_corr_mat

def plot_corr_mat_save_wrap(df_X:pd.DataFrame, title:str,
                            dir_out_viz_base:str | Path,
                            ds:str)-> matplotlib.figure.Figure:
    """Wrapper to plot and save the dataset correlation matrix

    :param df_X: The full dataset of interest, e.g. used for training/validation
    :type df_X: pd.DataFrame
    :param title: Title to place in the correlation matrix plot
    :type title: str
    :param dir_out_viz_base: base directory for saving visualization
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The dataset name to use in plot title and filename
    :type ds: str
    :return: The correlation matrix plot
    :rtype: matplotlib.figure.Figure
    """
    fig_corr_mat = plot_corr_mat(df_X, title)
    path_corr_mat = std_corr_mat_plot_path(dir_out_viz_base,ds)
    fig_corr_mat.savefig(path_corr_mat)
    logging.info(f"Wrote the {ds} dataset correlation matrix to:\n{path_corr_mat}")
    return fig_corr_mat

def std_corr_path(dir_out_anlys_base: str|Path, ds:str,
                   cstm_str:str=None) -> pathlib.PosixPath:
    """Standardize the filepath that saves correlated attributes

    :param dir_out_anlys_base: The standardized analysis output directory
    :type dir_out_anlys_base: str | os.PathLike
    :param ds: the dataset name
    :type ds: str
    :param cstm_str: The option to add in a custom string such as the correlation threshold, defaults to None
    :type cstm_str: str, optional
    :return: Full filepath for saving correlated attributes table
    :rtype: pathlib.PosixPath
    """
    # TODO generate a file of the correlated attributes:
    if cstm_str:
        path_corr_attrs = Path(f"{dir_out_anlys_base}/{ds}/correlated_attrs_{ds}_{cstm_str}.csv")
    else:
        path_corr_attrs = Path(f"{dir_out_anlys_base}/{ds}/correlated_attrs_{ds}.csv")
    path_corr_attrs.parent.mkdir(parents=True,exist_ok=True)
    return path_corr_attrs

def corr_attrs_thr_table(df_X:pd.DataFrame, 
                        corr_thr:float = 0.8) -> pd.DataFrame:
    """Create a table of correlated attributes exceeding a threshold, with correlation values

    :param df_X: The attribute dataset
    :type df_X: pd.DataFrame
    :param corr_thr: The correlation threshold, between 0 & 1. Absolute values above this should be reduced, defaults to 0.8
    :type corr_thr: float, optional
    :return: The table of attribute pairings whose absolute correlations exceed a threshold
    :rtype: pd.DataFrame
    """
    df_corr = df_X.corr()

    # TODO Change code to selecting upper triangle of correlation matrix
    upper = df_corr.abs().where(np.triu(np.ones(df_corr.shape), k=1).astype(bool))

    # Find attributes with correlation greater than a certain threshold
    row_idx, col_idx = np.where(df_corr.abs() > corr_thr)
    df_corr_rslt = pd.DataFrame({'attr1': df_corr.columns[row_idx],
                'attr2': df_corr.columns[col_idx],
                'corr' : [df_corr.iat[row, col] for row, col in zip(row_idx, col_idx)]
                })
    # Remove the identical attributes
    df_corr_rslt = df_corr_rslt[df_corr_rslt['attr1']!= df_corr_rslt['attr2']].drop_duplicates()
    return df_corr_rslt

def write_corr_attrs_thr(df_corr_rslt:pd.DataFrame,path_corr_attrs: str | Path):
    """Wrapper to generate high correlation pairings table and write to file

    :param df_corr_rslt: _description_
    :type df_corr_rslt: pd.DataFrame
    :param path_corr_attrs: csv write path
    :type path_corr_attrs: str | os.PathLike
    """

    df_corr_rslt.to_csv(path_corr_attrs) # INSPECT THIS FILE 
    logging.info(f"Wrote highly correlated attributes to {path_corr_attrs}")
    logging.info("The user may now inspect the correlated attributes and make decisions on which ones to exclude")

def corr_thr_write_table_wrap(df_X:pd.DataFrame,dir_out_anlys_base:str|Path,
                              ds:str,corr_thr:float=0.8)->pd.DataFrame:
    """Wrapper to generate high correlation pairings table above an absolute threshold of interest and write to file
    
    :param df_X: The attribute dataset
    :type df_X: pd.DataFrame
    :param dir_out_anlys_base: The standard analysis directory
    :type path_corr_attrs: str | os.PathLike
    :param ds: The dataset name
    :type ds: str
    :param corr_thr: The correlation threshold, between 0 & 1. Absolute values above this detected, defaults to 0.8
    :type corr_thr: float, optional
    :return: The table of attribute pairings whose absolute correlations exceed a threshold
    :rtype: pd.DataFrame
    """
    # Generate the paired table of attributes correlated above an absolute threshold
    df_corr_rslt = corr_attrs_thr_table(df_X,corr_thr)
    path_corr_attrs_cstm = std_corr_path(dir_out_anlys_base=dir_out_anlys_base,
                                          ds=ds,
                                         cstm_str=f'thr{corr_thr}') 
    write_corr_attrs_thr(df_corr_rslt,path_corr_attrs_cstm)
    return df_corr_rslt

def pca_stdscaled_tfrm(df_X:pd.DataFrame, 
                       std_scale:bool=True
                       )->PCA:
    """Generate the PCA object, and perform a standardized scaler transformation if desired

    :param df_X: Dataframe of attribute data
    :type df_X: pd.DataFrame
    :param std_scale: Should the data be standard scaled?, defaults to True
    :type std_scale: bool, optional
    :return: The principal components analysis object
    :rtype: PCA
    """
    
    # Fit using the scaled data
    if std_scale:
        scaler = StandardScaler().fit(df_X)
        df_X_scaled = pd.DataFrame(scaler.transform(df_X), index=df_X.index.values, columns=df_X.columns.values)
    else:
        df_X_scaled = df_X.copy()
    pca_scaled = PCA()
    pca_scaled.fit(df_X_scaled)
    #cpts_scaled = pd.DataFrame(pca.transform(df_X_scaled))

    return pca_scaled

def plot_pca_stdscaled_tfrm(pca_scaled:PCA, 
                            title:str = 'Explained Variance Ratio by Principal Component',
                            std_scale:bool=True)-> matplotlib.figure.Figure:
    """Generate variance explained by PCA plot

    :param pca_scaled:  The PCA object generated from dataset
    :type pca_scaled: PCA
    :param title: plot title, defaults to 'Explained Variance Ratio by Principal Component'
    :type title: str, optional
    :param std_scale: Have the data been standardized,, defaults to True
    :type std_scale: bool, optional
    :return: Plot of the variance explained by PCA
    :rtype: matplotlib.figure.Figure
    """
    
    if std_scale:
        xlabl = 'Principal Component of Standardized Data'
    else:
        xlabl = 'Principal Component'
    # Create the plot for explained variance ratio
    x_axis = np.arange(1, pca_scaled.n_components_ + 1)
    plt.figure(figsize=(10, 6))
    plt.plot(x_axis, pca_scaled.explained_variance_ratio_, marker='o', linestyle='--', color='b')
    plt.xlabel(xlabl)
    plt.ylabel('Explained Variance Ratio')
    plt.title(title)
    plt.xticks(x_axis)
    plt.grid(True)

    fig = plt.gcf()
    return fig

def plot_pca_stdscaled_cumulative_var(pca_scaled:PCA, 
                                      title='Cumulative Proportion of Variance Explained vs Principal Components',
                                      std_scale:bool=True) -> matplotlib.figure.Figure:
    """Generate cumulative variance PCA plot

    :param pca_scaled: The PCA object
    :type pca_scaled: PCA
    :param title: plot title, defaults to 'Cumulative Proportion of Variance Explained vs Principal Components'
    :type title: str, optional
    :param std_scale: Have the data been standardized, defaults to True
    :type std_scale: bool, optional
    :return: Plot of the cumulative PCA variance
    :rtype: matplotlib.figure.Figure
    """
    if std_scale:
        xlabl = 'Principal Component of Standardized Data'
    else:
        xlabl = 'Principal Component'

    # Calculate the cumulative variance explained
    cumulative_variance_explained = np.cumsum(pca_scaled.explained_variance_ratio_)
    x_axis = np.arange(1, pca_scaled.n_components_ + 1)

    # Create the plot for cumulative proportion of variance explained
    plt.figure(figsize=(10, 6))
    plt.plot(x_axis, cumulative_variance_explained, marker='o', linestyle='-', color='b')
    plt.xlabel(xlabl)
    plt.ylabel('Cumulative Proportion of Variance Explained')
    plt.title(title)
    plt.xticks(x_axis)
    plt.grid(True)

    fig = plt.gcf()
    return fig 


def std_pca_plot_path(dir_out_viz_base: str|Path,
                      ds:str, cstm_str:str=None
                      ) -> pathlib.PosixPath:
    """Standardize the filepath for saving principal component analysis plots

    :param dir_out_viz_base: The base visualization output directory
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The dataset name
    :type ds: str
    :param cstm_str: The option to add in a custom string such as the plot type, defaults to None, defaults to None
    :type cstm_str: str, optional
    :return: The PCA plot filepath
    :rtype: pathlib.PosixPath
    """
    if cstm_str:
        path_pca_plot = Path(f"{dir_out_viz_base}/{ds}/correlation_matrix_{ds}_{cstm_str}.png")
    else:
        path_pca_plot = Path(f"{dir_out_viz_base}/{ds}/correlation_matrix_{ds}.png")
    path_pca_plot.parent.mkdir(parents=True,exist_ok=True)

    return path_pca_plot


def plot_pca_save_wrap(df_X:pd.DataFrame, 
                        dir_out_viz_base:str|Path,
                        ds:str, 
                        std_scale:bool=True)->PCA:
    """Wrapper function to generate PCA plots on dataset

    :param df_X: The attribute dataset of interest
    :type df_X: pd.DataFrame
    :param dir_out_viz_base: Standardized output directory for visualization
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The dataset name
    :type ds: str
    :param std_scale: Should dataset be standardized using StandardScaler, defaults to True
    :type std_scale: bool, optional
    :return: The principal components analysis object
    :rtype: PCA
    """
    # CREATE THE EXPLAINED VARIANCE RATIO PLOT
    cstm_str = ''
    if std_scale:
        cstm_str = 'std_scaled'
    pca_scaled = pca_stdscaled_tfrm(df_X,std_scale)
    fig_pca_stdscale = plot_pca_stdscaled_tfrm(pca_scaled)
    path_pca_stdscaled_fig = std_pca_plot_path(dir_out_viz_base,ds,cstm_str=cstm_str)
    fig_pca_stdscale.savefig(path_pca_stdscaled_fig)
    logging.info(f"Wrote the {ds} PCA explained variance ratio plot to\n{path_pca_stdscaled_fig}")
    plt.clf()
    plt.close()
    # CREATE THE CUMULATIVE VARIANCE PLOT
    cstm_str_cum = 'cumulative_var'
    if std_scale:
        cstm_str_cum = 'cumulative_var_std_scaled'
    path_pca_stdscaled_cum_fig = std_pca_plot_path(dir_out_viz_base,ds,cstm_str=cstm_str_cum)
    fig_pca_cumulative = plot_pca_stdscaled_cumulative_var(pca_scaled)
    fig_pca_cumulative.savefig(path_pca_stdscaled_cum_fig)
    logging.info(f"Wrote the {ds} PCA cumulative variance explained plot to\n{path_pca_stdscaled_cum_fig}")
    plt.clf()
    plt.close('all')
    gc.collect()
    return None

def plot_feature_importance(feat_imprt:np.ndarray, attrs:Iterable[str],
                        title:str) -> Figure:
    """Generate the feature importance plot

    :param feat_imprt: Feature importance array from `rfr.feature_importances_`
    :type feat_imprt: np.ndarray
    :param attrs: The catchment attributes of interest
    :type attrs: Iterable[str]
    :param title: The feature importance plot title
    :type title: str
    :return: The feature importance plot
    :rtype: Figure
    """
    df_feat_imprt = pd.DataFrame({'attribute': attrs,
                                'importance': feat_imprt}).sort_values(by='importance', ascending=False)
    # Calculate the correlation matrix
    plt.figure(figsize=(10,6))
    plt.barh(df_feat_imprt['attribute'], df_feat_imprt['importance'])
    plt.xlabel('Importance')
    plt.ylabel('Attribute')
    plt.title(title)

    fig = plt.gcf()
    return fig

def save_feat_imp_fig_wrap(model:any,
                           attrs: Iterable[str],
                           dir_out_viz_base:str|Path,
                           ds:str, metr:str, algo_str:str):
    """Wrapper to generate & save to file the feature importance plot

    :param model: The trained regressor/classifier object containing .feature_importances_
    :type model: any
    :param attrs: The attributes 
    :type attrs: Iterable[str]
    :param dir_out_viz_base: The standard output base directory for visualizations
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable of interest
    :type metr: str
    :param algo_str: The algorithm string identifier (e.g. 'xgb', 'rf')
    :type algo_str: str
    """ 
    # Changelog/contributions
    #     FY25 - originally created, GL
    #     2026-08-14 refactor: generalize to other algoirthm strings, Gemni3.1Pro

    feat_imprt = getattr(model, "feature_importances_", None)
    
    if feat_imprt is None:
        logging.warning(f"Model {algo_str} does not contain .feature_importances_")
        return
        
    # Generate dynamic title
    title_imp = f"{algo_str.upper()} feature importance of {metr}: {ds}"
    
    # Use the renamed core plotting function
    fig_feat_imp = plot_feature_importance(feat_imprt, attrs=attrs, title=title_imp)

    # Generate dynamic save path (e.g., 'xgb_feature_importance_...')
    path_fig_imp = std_feat_imp_path(dir_out_viz_base=dir_out_viz_base,
                      ds=ds, algo_str=algo_str, metr=metr)
    path_fig_imp.parent.mkdir(parents=True, exist_ok=True)

    fig_feat_imp.savefig(path_fig_imp)
    logging.info(f"Wrote feature importance plot to {path_fig_imp}")
    
    plt.close(fig_feat_imp)
    plt.close('all')
    gc.collect()

def std_feat_imp_path(dir_out_viz_base: str|Path,
                      ds:str, algo_str:str, metr:str):
    path_fig_imp = Path(dir_out_viz_base) / ds / f"{algo_str}_feature_importance_{ds}_{metr}.png"
    path_fig_imp.parent.mkdir(parents=True, exist_ok=True)
    return path_fig_imp

def std_lc_plot_path(dir_out_viz_base: str|Path,
                      ds:str, metr:str, algo_str:str
                      ) -> pathlib.PosixPath:

    path_lc_plot = Path(f"{dir_out_viz_base}/{ds}/learning_curve_{ds}_{metr}_{algo_str}.png")
    path_lc_plot.parent.mkdir(parents=True,exist_ok=True)
    return path_lc_plot

def std_regr_pred_obs_path(dir_out_viz_base:str|Path, ds:str,
                            metr:str,algo_str:str,
                            split_type:str='') -> pathlib.PosixPath:
    """Generate a filepath of the predicted vs observed regresion plot

    :param dir_out_viz_base: The base directory for saving plots
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable of interest
    :type metr: str
    :param algo_str: The type of algorithm used to create predictions
    :type algo_str: str
    :param split_type: The type of data being displayed (e.g. training, testing), defaults to ''
    :type split_type: str, optional
    :return: The path to save the regression of predicted vs observed values.
    :rtype: pathlib.PosixPath
    """

    path_regr_pred_plot = Path(f"{dir_out_viz_base}/{ds}/regr_pred_obs_{ds}_{metr}_{algo_str}_{split_type}.png")
    path_regr_pred_plot.parent.mkdir(parents=True,exist_ok=True)
    return path_regr_pred_plot

def std_regr_pred_obs_path_mapie(dir_out_viz_base:str|Path, ds:str,
                            metr:str,algo_str:str,alpha_val:float,
                            split_type:str='') -> pathlib.PosixPath:
    """Generate a filepath of the predicted vs observed regresion plot

    :param dir_out_viz_base: The base directory for saving plots
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable of interest
    :type metr: str
    :param algo_str: The type of algorithm used to create predictions
    :type algo_str: str
    :param split_type: The type of data being displayed (e.g. training, testing), defaults to ''
    :type split_type: str, optional
    :return: The path to save the regression of predicted vs observed values.
    :rtype: pathlib.PosixPath
    """

    path_regr_pred_plot = Path(f"{dir_out_viz_base}/{ds}/regr_pred_obs_{ds}_{metr}_{algo_str}_{split_type}_alpha{alpha_val}.png")
    path_regr_pred_plot.parent.mkdir(parents=True,exist_ok=True)
    return path_regr_pred_plot

def _estimate_decimals_for_plotting(val:float)-> int:
    """Determine how many decimals should be used when rounding
    :param val: The value of interest for rounding
    :type val: np.float
    :return: The number of decimal places to round to
    :rtype: int
    """

    fmt_positional = np.format_float_positional(val)
    round_decimals = 2
    if fmt_positional[0:2] == '0.':
        sub_fmt_positional = fmt_positional[2:]
        count = 0
        for char in sub_fmt_positional:
            if char == '0':
                count += 1
            else:
                round_decimals = count+3
                break

    return round_decimals

def plot_pred_vs_obs_regr(y_pred: np.ndarray, y_obs: np.ndarray, ds:str, metr:str, 
                          r2_val:float=None,spearman_val:float=None)->Figure:
    """Plot the observed vs. predicted module performance

    :param y_pred: The predicted response variable
    :type y_pred: np.ndarray
    :param y_obs: The observed response variable
    :type y_obs: np.ndarray
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable name of interest
    :type metr: str
    :param r2_val: The r-squared value from regression
    :type r2_val: float
    :param spearman_val: The spearman rank correlation coefficient
    :type spearman_val: float
    :return: The predicted vs observed regression plot
    :rtype: Figure
    """
    max_val = np.max([y_pred,y_obs])
    tot_rnd_max = _estimate_decimals_for_plotting(max_val)
    min_val = np.min([y_pred,y_obs])
    tot_rnd_min = _estimate_decimals_for_plotting(min_val)
    tot_rnd = np.max([tot_rnd_max,tot_rnd_min])
    min_val_rnd = np.round(np.min([min_val,0]),tot_rnd)
    max_val_rnd = np.round(max_val,tot_rnd)
    min_vals = (min_val_rnd,min_val_rnd)
    max_vals = (max_val_rnd,max_val_rnd)

    # Adapted from plot in bolotinl's rafts_perf_viz.py
    plt.scatter(x=y_obs,y=y_pred,alpha=0.3)
    plt.axline(min_vals, max_vals, color='black', linestyle='--')
    plt.ylabel('Predicted {}'.format(metr))
    plt.xlabel('Actual {}'.format(metr))
    plt.title('RaFTS-predicted vs. observed: {}'.format(ds))

    metrics_text = []
    if r2_val is not None:
        metrics_text.append(f'$R^2 = {r2_val:.2f}$')

    if spearman_val is not None:
        metrics_text.append(f'$\\rho = {spearman_val:.2f}$')

    if metrics_text:
        plt.gca().text(0.05, 0.95, '\n'.join(metrics_text), transform=plt.gca().transAxes,
                       fontsize=12, verticalalignment='top', bbox=dict(facecolor='white', alpha=0.5))

    fig = plt.gcf()
    return fig

def plot_pred_vs_obs_wrap(y_pred: np.ndarray, y_obs:np.ndarray, dir_out_viz_base:str|Path,
                           ds:str, metr:str, algo_str:str, r2_val:float=None,
                           split_type:str='',spearman_val:float=None):
    """Wrapper to create & save predicted vs. observed regression plot

    :param y_pred: The predicted response variable
    :type y_pred: np.ndarray
    :param y_obs: The observed response variable
    :type y_obs: np.ndarray
    :param dir_out_viz_base: The base directory for saving plots
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable name of interest
    :type metr: str
    :param algo_str: The type of algorithm used to create predictions
    :type algo_str: str
    :param split_type: The type of data being displayed (e.g. training, testing), defaults to ''
    :type split_type: str, optional
    :param r2_val: The r-squared value from regression
    :type r2_val: float
    :param spearman_val: The spearman rank correlation coefficient
    :type spearman_val: float
    """
    # Generate figure
    fig_regr = plot_pred_vs_obs_regr(y_pred, y_obs, ds, metr, r2_val,spearman_val)
    # Generate filepath for saving figure
    path_regr_plot = std_regr_pred_obs_path(dir_out_viz_base, ds,
                            metr,algo_str,split_type)
    # Save the plot as a .png file
    fig_regr.savefig(path_regr_plot, dpi=300, bbox_inches='tight')
    plt.close(fig_regr)
    plt.close('all')
    gc.collect()

def plot_pred_vs_obs_regr_mapie(y_pred: np.ndarray, y_obs: np.ndarray, ds:str,
                                metr:str, y_pis: list, alpha_val:float,
                                r2_val:float=None,spearman_val:float=None)->Figure:
    """Plot the observed vs. predicted module performance

    :param y_pred: The predicted response variable
    :type y_pred: np.ndarray
    :param y_obs: The observed response variable
    :type y_obs: np.ndarray
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable name of interest
    :type metr: str
    :param y_pis: y prediction intervals
    :type y_pis: list
    :param alpha_val: The alpha value for the prediction intervals
    :type alpha_val: float
    :param r2_val: The r-squared value from regression
    :type r2_val: float
    :param spearman_val: The spearman rank correlation coefficient
    :type spearman_val: float
    :return: The predicted vs observed regression plot
    :rtype: Figure
    """
    max_val = np.max([y_pred,y_obs])
    tot_rnd_max = _estimate_decimals_for_plotting(max_val)
    min_val = np.min([y_pred,y_obs])
    tot_rnd_min = _estimate_decimals_for_plotting(min_val)
    tot_rnd = np.max([tot_rnd_max,tot_rnd_min])
    min_val_rnd = np.round(np.min([min_val,0]),tot_rnd)
    max_val_rnd = np.round(max_val,tot_rnd)
    min_vals = (min_val_rnd,min_val_rnd)
    max_vals = (max_val_rnd,max_val_rnd)

    # Extract error bars (lower and upper limits) for the first alpha value
    lower_err = np.abs(y_pred - np.array([y_pis[i].loc['lower_limit', f'alpha_{alpha_val:.2f}'] for i in range(len(y_pred))]))
    upper_err = np.abs(np.array([y_pis[i].loc['upper_limit', f'alpha_{alpha_val:.2f}'] for i in range(len(y_pred))]) - y_pred)
    
    # Adapted from plot in bolotinl's rafts_perf_viz.py
    plt.errorbar(y_obs, y_pred, yerr=[lower_err, upper_err], fmt='o', alpha=0.3, ecolor='gray', capsize=3)
    plt.axline(min_vals, max_vals, color='black', linestyle='--')
    plt.ylabel('Predicted {}'.format(metr))
    plt.xlabel('Actual {}'.format(metr))
    plt.title('RaFTS-predicted vs. observed: {}'.format(ds))

    # Add alpha values as text box
    plt.gca().text(0.05, 0.95, f'alpha = {alpha_val:.2f}', transform=plt.gca().transAxes,
                   fontsize=10, verticalalignment='bottom', horizontalalignment='right',
                   bbox=dict(facecolor='white', alpha=0.5))
    metrics_text = []
    if r2_val is not None:
        metrics_text.append(f'$R^2 = {r2_val:.2f}$')

    if spearman_val is not None:
        metrics_text.append(f'$\\rho = {spearman_val:.2f}$')

    if metrics_text:
        plt.gca().text(0.05, 0.95, '\n'.join(metrics_text), transform=plt.gca().transAxes,
                       fontsize=12, verticalalignment='top', bbox=dict(facecolor='white', alpha=0.5))
    fig = plt.gcf()
    return fig

def plot_pred_vs_obs_wrap_mapie(y_pred: np.ndarray, y_obs:np.ndarray, dir_out_viz_base:str|Path,
                           ds:str, metr:str, algo_str:str,y_pis: list, alpha_val:float,
                           split_type:str='',r2_val:float=None,spearman_val:float=None):
    """Wrapper to create & save predicted vs. observed regression plot

    :param y_pred: The predicted response variable
    :type y_pred: np.ndarray
    :param y_obs: The observed response variable
    :type y_obs: np.ndarray
    :param dir_out_viz_base: The base directory for saving plots
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable name of interest
    :type metr: str
    :param algo_str: The type of algorithm used to create predictions
    :type algo_str: str
    :param split_type: The type of data being displayed (e.g. training, testing), defaults to ''
    :type split_type: str, optional
    :param r2_val: The r-squared value from regression
    :type r2_val: float
    :param spearman_val: The spearman rank correlation coefficient
    :type spearman_val: float
    """
    # Generate figure
    fig_regr = plot_pred_vs_obs_regr_mapie(y_pred, y_obs, ds, metr, y_pis, alpha_val, r2_val,spearman_val)
    # Generate filepath for saving figure
    path_regr_plot = std_regr_pred_obs_path_mapie(dir_out_viz_base, ds,
                            metr,algo_str,alpha_val,split_type)
    # Save the plot as a .png file
    fig_regr.savefig(path_regr_plot, dpi=300, bbox_inches='tight')
    plt.close(fig_regr)
    plt.close('all')
    gc.collect()

def std_map_pred_path(dir_out_viz_base:str|Path, ds:str,
                      metr:str,algo_str:str,
                      split_type:str='') -> pathlib.PosixPath:
    """Generate a filepath of the predicted response variables map:

    :param dir_out_viz_base: The base directory for saving plots
    :type dir_out_viz_base: str | os.PathLike
    :param ds: The unique dataset name
    :type ds: str
    :param metr: The metric/response variable of interest
    :type metr: str
    :param algo_str: The type of algorithm used to create predictions
    :type algo_str: str
    :param split_type: The type of data being displayed (e.g. training, testing), defaults to ''
    :type split_type: str, optional
    :return: _description_
    :rtype: pathlib.PosixPath
    """
    
    # 
    path_pred_map_plot = Path(f"{dir_out_viz_base}/{ds}/prediction_map_{ds}_{metr}_{algo_str}_{split_type}.png")
    path_pred_map_plot.parent.mkdir(parents=True,exist_ok=True)
    return path_pred_map_plot

def gen_conus_basemap(dir_out_basemap:str | Path, # This should be the data_visualizations directory
                    url:str = 'https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_500k.zip',
                    fn_basemap:str='cb_2018_us_state_500k.shp') -> gpd.geodataframe.GeoDataFrame:
    """Retrieve the basemap for CONUS

    :param dir_out_basemap: The standard directory for saving the CONUS basemap
    :type dir_out_basemap: str | os.PathLike
    :param url: The url of a basemap of interest
    :type url: str
    :param fn_basemap: The filename to use for saving basemap, defaults to 'cb_2018_us_state_500k.shp'
    :type fn_basemap: str, optional
    :return: The geopandas dataframe of the basemap
    :rtype: gpd.geodataframe.GeoDataFrame
    """
    # Changelog / contributions:
    #     2024 Originally created
    #     2025-09-22, changed from using urlib to using requests to avoid SSL error, GL


    #url = 'https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_500k.zip'
    path_zip_basemap = f'{dir_out_basemap}/cb_2018_us_state_500k.zip'
    path_shp_basemap = f'{dir_out_basemap}/{fn_basemap}'

    if not Path(path_zip_basemap).exists():
        logging.info("Downloading shapefile...")
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, verify=False)  # disable SSL verification
        with open(path_zip_basemap, "wb") as out_file:
            out_file.write(response.content)
        logging.info("Shapefile downloaded.")

    if not Path(path_shp_basemap).exists():
        with zipfile.ZipFile(path_zip_basemap, "r") as zip_ref:
            zip_ref.extractall(path_shp_basemap)

    states = gpd.read_file(path_shp_basemap)
    states = states.to_crs("EPSG:4326")

    return states
    
def plot_map_pred(geo_df:gpd.GeoDataFrame, states:gpd.GeoDataFrame,
                  title:str,metr:str,colname_data:str='prediction',
                  plot_style:str='auto', task_type:str='regression'
                  )->Figure:
    # Calculate vmin and vmax based on the data
    vmin = geo_df[colname_data].min(skipna=True)
    vmax = geo_df[colname_data].max(skipna=True)

    fig, ax = plt.subplots(1, 1, figsize=(20, 24))

    # Determine plot style
    if plot_style == 'auto':
        plot_style = 'hexbin' if geo_df.shape[0] > 20000 else 'points'
    map_msg = f"{title} :\n \
        - Plotting {geo_df.shape[0]} locations on map with {plot_style} style and {task_type} task_type"
    logging.info(map_msg)
    print(map_msg)
    # --- 1. HEXBIN PLOTTING ---
    if plot_style == 'hexbin':
        logging.info(f"Using hexbin mapping for large dataset ({len(geo_df)} points).")
        
        if task_type == 'clustering':
            # Use mode for discrete categories and a discrete colormap
            reduce_C_func = lambda x: pd.Series(x).mode()[0] if len(x) > 0 else np.nan
            cmap_choice = 'tab20'
        else:
            # Use mean for continuous regression and a continuous colormap
            reduce_C_func = np.mean
            cmap_choice = 'viridis'

        hb = ax.hexbin(
            x=geo_df.geometry.centroid.x, 
            y=geo_df.geometry.centroid.y, 
            C=geo_df[colname_data], 
            reduce_C_function=reduce_C_func, 
            gridsize=150, 
            cmap=cmap_choice, 
            vmin=vmin, vmax=vmax, 
            zorder=2, alpha=0.9, edgecolors='none'
        )
        cbar_mappable = hb

        if task_type == 'clustering':
            unique_clusters = sorted(geo_df[colname_data].dropna().unique())
            cmap = plt.get_cmap(cmap_choice)
            norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)
            
            # Map the exact color assigned to each cluster and create a patch for it
            legend_elements = [
                mpatches.Patch(color=cmap(norm(val)), label=f'Cluster {int(val)}') 
                for val in unique_clusters
            ]
            ax.legend(handles=legend_elements, title="Clusters", prop={'size': 20}, 
                      title_fontsize=24, loc='lower right')

    # --- 2. POINTS PLOTTING ---
    else: 
        if task_type == 'clustering':
            logging.info("Using categorical point mapping for cluster labels.")
            geo_df.plot(column=colname_data, ax=ax, categorical=True, cmap='tab20', 
                        legend=True, markersize=150, zorder=2)
            
            # Customize the discrete legend
            legend = ax.get_legend()
            if legend:
                legend.set_title("Clusters", prop={'size': 24})
                for text in legend.get_texts():
                    text.set_fontsize(20)
        else:
            logging.info("Using continuous point mapping.")
            ms = 150 if len(geo_df) < 10000 else max(0.5, 500000 / len(geo_df))
            geo_df.plot(column=colname_data, ax=ax, markersize=ms, cmap='viridis', legend=False, zorder=2)
            cbar_mappable = plt.cm.ScalarMappable(norm=matplotlib.colors.Normalize(vmin=vmin, vmax=vmax), cmap='viridis')

    # Plot states boundary once for both styles
    states.boundary.plot(ax=ax, color="#555555", linewidth=1, zorder=1, alpha=0.5)  

    # Formatting
    ax.tick_params(axis='x', labelsize= 24)
    ax.tick_params(axis='y', labelsize= 24)
    plt.xlabel('Longitude',fontsize = 26) 
    plt.ylabel('Latitude',fontsize = 26)  
    
    # Only draw the continuous colorbar for regression tasks
    if task_type != 'clustering':
        cbar_ax = plt.colorbar(cbar_mappable, ax=ax,fraction=0.02, pad=0.04)
        cbar_ax.set_label(label=metr,size=24)
        cbar_ax.ax.tick_params(labelsize=24) 
    
    plt.title(title, fontsize = 28)
    bounds = geo_df.total_bounds
    x_buffer = (bounds[2] - bounds[0]) * 0.05
    y_buffer = (bounds[3] - bounds[1]) * 0.05
    if x_buffer == 0: x_buffer = 1.0 
    if y_buffer == 0: y_buffer = 1.0
    ax.set_xlim(bounds[0] - x_buffer, bounds[2] + x_buffer)
    ax.set_ylim(bounds[1] - y_buffer, bounds[3] + y_buffer)
    fig = plt.gcf()

    return fig

def plot_map_pred_wrap(test_gdf:gpd.GeoDataFrame,
                       dir_out_viz_base:str | os.PathLike, 
                      ds:str,
                      metr:str,algo_str:str,
                      split_type:str='test',
                      colname_data:str='prediction',
                      epsg_reproj:int=3857,
                      task_type:str='regression'):
    """Wrapper for plotting map displays

    :param test_gdf: The geodataframe to plotting on maps
    :type test_gdf: gpd.GeoDataFrame
    :param dir_out_viz_base: The base directory for storing visualization data
    :type dir_out_viz_base: str|os.PathLike
    :param ds: The dataset name
    :type ds: str
    :param metr: The response variable of interest
    :type metr: str
    :param algo_str: The algorithm shortstring
    :type algo_str: str
    :param split_type: The type of data, either algo testing or actual prediction, defaults to 'test'
    :type split_type: str, optional
    :param colname_data: The standard colname for data values in `test_gdf`, defaults to 'prediction'
    :type colname_data: str, optional
    :param epsg_reproj: The EPSG code for reprojecting data for map display, defaults to 3857
    :type epsg_reproj: int
    """

    path_pred_map_plot = std_map_pred_path(dir_out_viz_base,ds,metr,algo_str,split_type)
    dir_out_basemap = path_pred_map_plot.parent.parent
    states = gen_conus_basemap(dir_out_basemap = dir_out_basemap)

    # TODO add option to print oconus basemap
    # TODO change epsg_reproj for oconus basemap

    # Ensure the gdf matches the 4326 epsg used for states:
    test_gdf = test_gdf.to_crs(4326)

    # Re-project for visualization
    states = states.to_crs(epsg=epsg_reproj)
    geo_df = test_gdf.to_crs(epsg=epsg_reproj)
    geo_df_valid = geo_df[~geo_df.geometry.is_empty]
    if geo_df_valid.shape[0] < geo_df.shape[0]:
        logging.warning(f"Lost a total {geo_df.shape[0]-geo_df_valid.shape[0]} \
                         of {geo_df.shape[0]} data rows due to invalid geometries")
        if colname_data in geo_df_valid.columns:
            geo_df_valid = geo_df_valid.dropna(subset=[colname_data])
        geo_df_valid = geo_df_valid.reset_index(drop=True)
        geo_df = geo_df_valid.copy()

    # Generate the map
    plot_title = f"Predicted Values: {metr} - {ds}: {algo_str} algorithm"
    plot_pred_map = plot_map_pred(geo_df=geo_df, states=states,title=plot_title,
                                  metr=metr,colname_data=colname_data,
                                  task_type=task_type)

    # Save the plot as a .png file
    plot_pred_map.savefig(path_pred_map_plot, dpi=300, bbox_inches='tight')
    logging.info(f"Wrote prediction map to \n{path_pred_map_plot}")
    plt.close(plot_pred_map)
    plt.close('all')
    gc.collect()

def plot_map_pred_uncn(geo_df: gpd.GeoDataFrame, states: gpd.GeoDataFrame, title: str, metr: str,
                       alpha_val: float = None, uncn_col: str = None,
                       colname_data: str = 'prediction'):
    """Generate a map where color = prediction value, and size = uncertainty variance/spread."""
    
    # 1. Fetch errors dynamically based on the requested uncertainty method
    if alpha_val is not None:
        err_dict = raftsutil.infer_mapie_errors(geo_df, alpha_val, colname_data)
        uncn_series = err_dict['total_err']
        min_err, max_err = err_dict['min_err'], err_dict['max_err']
        legend_title = f"{(1 - alpha_val) * 100:.0f}% MAPIE CI Range"
    elif uncn_col is not None and uncn_col in geo_df.columns:
        uncn_series = geo_df[uncn_col]
        min_err, max_err = uncn_series.min(), uncn_series.max()
        legend_title = "ForestCI Variance"
    else:
        raise ValueError("Must provide either a valid alpha_val for MAPIE or a valid uncn_col for ForestCI.")

    # 2. Normalize marker size (scale from 100 to 400)
    if max_err > min_err:
        marker_sizes = 100 + 300 * (uncn_series - min_err) / (max_err - min_err)
    else:
        # Fallback if all points have the exact same uncertainty
        marker_sizes = pd.Series(200, index=geo_df.index)

    # 3. Plotting Setup
    fig, ax = plt.subplots(1, 1, figsize=(20, 24))
    states.boundary.plot(ax=ax, color="#555555", linewidth=1)
    
    # 4. Plot the data: Color by prediction, Size by Uncertainty
    geo_df.plot(column=colname_data, ax=ax, markersize=marker_sizes, cmap='viridis', legend=False, zorder=2)
    states.boundary.plot(ax=ax, color="#555555", linewidth=1, zorder=1)
    
    # 5. Add Colorbar for the Prediction Value
    vmin, vmax = geo_df[colname_data].min(), geo_df[colname_data].max()
    cbar = plt.cm.ScalarMappable(norm=matplotlib.colors.Normalize(vmin=vmin, vmax=vmax), cmap='viridis')
    cbar_ax = plt.colorbar(cbar, ax=ax, fraction=0.02, pad=0.04)
    cbar_ax.set_label(label=f"Predicted {metr}", size=24)
    cbar_ax.ax.tick_params(labelsize=24)

    plt.title(title, fontsize=28)

    # 6. Dynamic Map Bounds (with 5% buffer)
    bounds = geo_df.total_bounds
    x_buffer = (bounds[2] - bounds[0]) * 0.05
    y_buffer = (bounds[3] - bounds[1]) * 0.05
    if x_buffer == 0: x_buffer = 1.0 
    if y_buffer == 0: y_buffer = 1.0
    ax.set_xlim(bounds[0] - x_buffer, bounds[2] + x_buffer)
    ax.set_ylim(bounds[1] - y_buffer, bounds[3] + y_buffer)

    # 7. Scale Legend for the Uncertainty Circles
    legend_handles = [
        plt.scatter([], [], s=100, color='gray', label=f'{min_err:.2f}'),
        plt.scatter([], [], s=400, color='gray', label=f'{max_err:.2f}')
    ]
    ax.legend(handles=legend_handles, title=legend_title, 
              loc='lower left', fontsize=20, title_fontsize=22)

    return plt.gcf()

def plot_map_pred_wrap_uncn(test_gdf, dir_out_viz_base, ds, metr, algo_str,
                            alpha_val: float = None, uncn_col: str = None,
                            split_type='test', colname_data='prediction',
                            epsg_reproj: int = 3857):
    """Wrapper to handle file I/O, reprojection, and plotting for uncertainty maps."""
    
    # Standardize output filenames
    path_pred_map_plot = std_map_pred_path(dir_out_viz_base, ds, metr, algo_str, split_type)
    if alpha_val is not None:
        new_filename = path_pred_map_plot.stem + f"_mapie_alpha{alpha_val:.2f}" + path_pred_map_plot.suffix
    else:
        new_filename = path_pred_map_plot.stem + f"_{uncn_col}" + path_pred_map_plot.suffix
    path_uncn_plot = path_pred_map_plot.with_name(new_filename)
    
    dir_out_basemap = path_pred_map_plot.parent.parent
    states = gen_conus_basemap(dir_out_basemap=dir_out_basemap)

    # Safely Reproject
    test_gdf = test_gdf.to_crs(4326)
    states = states.to_crs(epsg=epsg_reproj)
    geo_df = test_gdf.to_crs(epsg=epsg_reproj)

    plot_title = f"Predicted Values and Uncertainty: {metr} - {ds}"
    plot_pred_map = plot_map_pred_uncn(geo_df=geo_df, states=states, title=plot_title,
                                       metr=metr, alpha_val=alpha_val, uncn_col=uncn_col,
                                       colname_data=colname_data)

    plot_pred_map.savefig(path_uncn_plot, dpi=300, bbox_inches='tight')
    logging.info(f"Wrote uncertainty map to \n{path_uncn_plot}")
    plt.close(plot_pred_map)
    plt.close('all')
    gc.collect()

def plot_best_perf_map(geo_df,states, title, comparison_col = 'dataset'):

    """Generate a map of the best-predicted response variables as determined from multiple datasets

    :param geo_df: Geodataframe of response variable results
    :type geo_df: gpd.GeoDataFrame
    :param states: The states basemap
    :type states: gpd.GeoDataFrame
    :param title: Map title
    :type title: str
    :param comparison_col: The geo_df column name representing data of interest, defaults to 'dataset'
    :type comparison_col: str, optional
    :return: Map of best-predicted response variables
    :rtype: Figure
    """
    fig, ax = plt.subplots(1, 1, figsize=(20, 24))
    base = states.boundary.plot(ax=ax, color="#555555", linewidth=1)


    # Plot points based on the 'best_algo' column
    geo_df.plot(column=comparison_col, ax=ax, markersize=150, cmap='viridis', legend=True,zorder=2)

    # Plot states boundary again with lower zorder
    states.boundary.plot(ax=ax, color="#555555", linewidth=1, zorder=1)

    # Set title and axis limits
    plt.title(title, fontsize=28)
    # Dynamically bound the map to the data points rather than the whole US basemap
    bounds = geo_df.total_bounds  # Returns [minx, miny, maxx, maxy]
    # Calculate a 5% spatial buffer so edge points aren't cut off by the plot borders
    x_buffer = (bounds[2] - bounds[0]) * 0.05
    y_buffer = (bounds[3] - bounds[1]) * 0.05
    # Fallback just in case all points share the exact same X or Y coordinate
    if x_buffer == 0: x_buffer = 1.0 
    if y_buffer == 0: y_buffer = 1.0
    ax.set_xlim(bounds[0] - x_buffer, bounds[2] + x_buffer)
    ax.set_ylim(bounds[1] - y_buffer, bounds[3] + y_buffer)

    # Customize the legend, specifically for the geo_df plot
    legend = ax.get_legend()
    if legend:
        legend.set_title("Formulations", prop={'size': 20})
        for text in legend.get_texts():
            text.set_fontsize(20)

    fig = plt.gcf()
    return fig

def std_map_best_path(dir_out_viz_base:str|Path,metr:str,ds:str
                      )->pathlib.PosixPath:
    """# Generate a filepath of the best-performing dataset map:

    :param dir_out_viz_base: _description_
    :type dir_out_viz_base: str | os.PathLike
    :param metr: The metric/response variable of interest
    :type metr: str
    :param ds: The unique dataset of interest
    :type ds: str
    :return: Path to the map figure in png
    :rtype: pathlib.PosixPath
    """
    
    path_best_map_plot = Path(f"{dir_out_viz_base}/{ds}/performance_map_best_formulation_{metr}.png")
    path_best_map_plot.parent.mkdir(parents=True,exist_ok=True)
    return path_best_map_plot


def plot_best_algo_wrap(geo_df, dir_out_viz_base,subdir_anlys, metr,comparison_col = 'dataset'):
    """Generate the map of the best performance across each formulation

    note:: saves the plot inside the directory {ds}
    """
    path_best_map_plot = std_map_best_path(dir_out_viz_base,metr,subdir_anlys)
    states = gen_conus_basemap(dir_out_basemap = dir_out_viz_base)
    title = f"Top predicted value: {metr}"

    plot_best_perf = plot_best_perf_map(geo_df, states,title, comparison_col)
    plot_best_perf.savefig(path_best_map_plot, dpi=300, bbox_inches='tight')
    logging.info(f"Wrote top predicted value map to \n{path_best_map_plot}")
    plt.close(plot_best_perf)
    plt.close('all')
    gc.collect()