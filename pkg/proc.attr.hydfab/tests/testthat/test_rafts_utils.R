#' @title Unit test RaFTS utilities that are not part of the standard attribute 
#' -grabbing functionality of RaFTS
#' @description Unit testing for RaFTS utility functions
#' @author Guy Litt \email{guy.litt@noaa.gov}
#' @note When running this script, be sure to also source tests/testthat/setup.R first
# Changelog / Contributions
#   2025-03-24 Originally created, GL

suppressPackageStartupMessages(library(proc.attr.hydfab,quietly=TRUE))
suppressPackageStartupMessages(library(testthat,quietly=TRUE))
suppressPackageStartupMessages(library(mockery,quietly=TRUE))
suppressPackageStartupMessages(library(dplyr,quietly=TRUE))
suppressPackageStartupMessages(library(arrow,quietly=TRUE))
suppressPackageStartupMessages(library(hydrofabric,quietly=TRUE))
suppressPackageStartupMessages(library(data.table,quietly=TRUE))
suppressPackageStartupMessages(library(fs,quietly=TRUE))
suppressPackageStartupMessages(library(sf,quietly=TRUE))
suppressPackageStartupMessages(library(future,quietly=TRUE))
suppressPackageStartupMessages(library(future.apply,quietly=TRUE))
suppressPackageStartupMessages(library(pkgcond,quietly=TRUE))
options(arrow.unsafe_metadata = TRUE)


# TODO establish a basic config file to read in for this functionality
comid <- "18094981"#"02479560"#14138870# A small basin
s3_base <- "s3://lynker-spatial/tabular-resources"
s3_bucket <- 'lynker-spatial'
s3_path_hydatl <- glue::glue('{s3_base}/hydroATLAS/hydroatlas_vars.parquet')


# Define data directories to a package-specific data path
dir_base <- system.file("extdata",package="proc.attr.hydfab")
# Refer to temp_dir <- tempdir() in setup.R
temp_dir <- local_temp_dir() # If running this on your own, source 'setup.R' first.
dir_db_hydfab <- file.path(temp_dir,'hfab')
path_meta <- paste0(temp_dir,"/{ds}/nldi_feat_{ds}_{ds_type}.{write_type}")
dir_db_attrs <- file.path(temp_dir,'attrs') # used for temporary attr retrieval
dir_db_attrs_pkg <- system.file("extdata","attributes_pah",package="proc.attr.hydfab")# permanent pacakage location
dir_user <- system.file("extdata","user_data_std", package="proc.attr.hydfab") # dir_user <- "~/git/fsds/pkg/proc.attr.hydfab/inst/extdata/user_data_std/"
dir_dataset <- file.path(dir_user,'xssa-mini')
path_mini_ds <- file.path(dir_dataset,'xSSA-mini_Raven_blended.nc')

ls_fs_std <- proc.attr.hydfab::proc_attr_read_gage_ids_fs(dir_dataset)

ha_vars <- c('pet_mm_s01', 'cly_pc_sav')#, 'cly_pc_uav') # hydroatlas variables
sc_vars <- c() # TODO look up variables. May need to select datasets first
usgs_vars <- c('TOT_TWI','TOT_PRSNOW')#,'TOT_POPDENS90','TOT_EWT','TOT_RECHG')

Retr_Params <- list(paths = list(dir_db_hydfab=dir_db_hydfab,
                                 dir_db_attrs=dir_db_attrs,
                                 s3_path_hydatl = s3_path_hydatl,
                                 dir_std_base = dir_user,
                                 path_meta=path_meta),
                    vars = list(usgs_vars = usgs_vars,
                                ha_vars = ha_vars),
                    datasets = 'xssa-mini',
                    write_type = 'parquet',
                    ds_type = 'training',
                    xtra_hfab = list(hf_version = "2.1.1",
                                     hfab_retr = FALSE,
                                     type='nextgen',
                                     domain='conus'
                    ))


# ---------------------------------------------------------------------------- #
# ------------------------------- UNIT TESTS --------------------------------- #
# ---------------------------------------------------------------------------- #
testthat::test_that('retrieve_attr_exst', {
  comids <- c("1520007","1623207","1638559","1722317") # !!Don't change this!!
  vars <- Retr_Params$vars %>% unlist() %>% unname()
  
  # Run tests based on expected dims
  dat_attr_all <- suppressWarnings(proc.attr.hydfab::retrieve_attr_exst(comids,vars,dir_db_attrs_pkg))
  testthat::expect_equal(length(unique(dat_attr_all$featureID)), # TODO update datasets inside dir_db_attrs
                         length(comids))
  testthat::expect_equal(length(unique(dat_attr_all$attribute)),length(vars))
  
  testthat::expect_error(proc.attr.hydfab::retrieve_attr_exst(comids,
                                                              vars,
                                                              dir_db_attrs='a'))
  # Testing for No parquet files present
  capt_no_parquet <- testthat::capture_condition(proc.attr.hydfab::retrieve_attr_exst(comids,
                                                                                      vars,
                                                                                      dir_db_attrs=dirname(dirname(dir_db_attrs_pkg))))
  testthat::expect_true(grepl("parquet",capt_no_parquet$message))
  nada_var <- testthat::capture_warnings(proc.attr.hydfab::retrieve_attr_exst(comids,vars=c("TOT_TWI","naDa"),
                                                                              dir_db_attrs_pkg))
  testthat::expect_true(any(grepl("naDa",nada_var)))
  
  nada_comid <- testthat::capture_warnings(proc.attr.hydfab::retrieve_attr_exst(comids=c("1520007","1623207","nada"),vars,
                                                                                dir_db_attrs_pkg))
  testthat::expect_true(any(base::grepl("nada",nada_comid)))
  
  testthat::expect_error(proc.attr.hydfab::retrieve_attr_exst(comids,vars=c(3134,3135),
                                                              dir_db_attrs_pkg))
  testthat::expect_warning(proc.attr.hydfab::retrieve_attr_exst(comids=c(3134,3135),vars,
                                                                dir_db_attrs_pkg))
})



testthat::test_that("dl_nhdplus_geoms_wrap", {
  
  filename_str <- 'test_rafts_utils'
  dir_save_nhdp <- file.path(temp_dir,"test_geoms_retr")
  names_nhdp_query <- c("catchment","flowlines","outlet","input_dt",
                        "path_gpkg_compiled")
  df <- data.frame(comids =c("1520007","1623207","1638559","1722317"),
                   idx=c(1,2,3,4))
  
  ################ Test an empty directory first #######################
  rslt_capt_cond <- testthat::capture_condition(
    proc.attr.hydfab:::compile_chunks_ndplus_geoms(dir_save_nhdp,
                                                   seq_nums=NULL,
                                                   filename_str=NULL))

  testthat::expect_true(base::grepl("No rds files",rslt_capt_cond$message))
  
  rslt_compile <- base::suppressWarnings(
    proc.attr.hydfab:::compile_chunks_ndplus_geoms(dir_save_nhdp,
                                                   seq_nums=NULL,
                                                   filename_str=NULL)) 
  testthat::expect_true(base::all(names_nhdp_query %in% names(rslt_compile)))
  
  
  ################ Test  #######################

  
  # Create with keep_cols = NULL
  rslt <- proc.attr.hydfab::dl_nhdplus_geoms_wrap(df=df,col_id="comids", 
                        dir_save_nhdp,filename_str = filename_str,
                        id_type = c("comid","AOI")[1],
                        keep_cols=c(NULL,"all")[1],
                        seq_size = nrow(df),
                        overwrite_chunk=FALSE)
  
  
  new_gpkg_in_dir <- list.files(dir_save_nhdp, pattern = filename_str) 
  new_gpkg_in_dir <- new_gpkg_in_dir[grep(pattern=".gpkg",x=new_gpkg_in_dir,fixed=TRUE)]
  path_gpkg <- file.path(dir_save_nhdp,new_gpkg_in_dir)
  testthat::expect_identical(names(rslt),names_nhdp_query)
  testthat::expect_true(base::any(base::grepl(filename_str,x = new_gpkg_in_dir)))
  layers_null_keep <- sf::st_layers(path_gpkg)
  testthat::expect_true(all(names_nhdp_query[1:3] %in% layers_null_keep$name))

  rslt_keep_all <- proc.attr.hydfab::dl_nhdplus_geoms_wrap(df=df,col_id="comids", 
                                                  dir_save_nhdp,
                                                  filename_str = filename_str,
                                                  id_type = c("comid","AOI")[1],
                                                  keep_cols="all",
                                                  # as long as seq_size is big, no waiting
                                                  seq_size = base::nrow(df)+5,
                                                  overwrite_chunk=FALSE)
  layers_null_keep_all <- sf::st_layers(path_gpkg)
  testthat::expect_true(base::all(names(rslt_keep_all) %in% names_nhdp_query))
  # Since keep_cols is 'all', the input_df should be written to gpkg
  testthat::expect_true('input_df' %in% layers_null_keep_all$name)
  
  ################ Test filled-in directory #######################

  
  rslt_compile_dat <- base::suppressWarnings(
    proc.attr.hydfab:::compile_chunks_ndplus_geoms(dir_save_nhdp,
                                                   seq_nums=NULL,
                                                   filename_str=NULL)) 
  testthat::expect_true(base::all(names_nhdp_query %in% base::names(rslt_compile_dat)))
  testthat::expect_identical(base::nrow(rslt_compile_dat$flowlines), 
                             base::nrow(df))
})