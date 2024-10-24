#' @title Unit test attribute grabber processor
#' @description Unit testing for catchment attribute grabbing via the hydrofabric
#' @author Guy Litt \email{guy.litt@noaa.gov}

# Changelog / Contributions
#   2024-07-24 Originally created, GL
#   2024-10-03 Contributed to, LB

# unloadNamespace("proc.attr.hydfab")
suppressPackageStartupMessages(library(proc.attr.hydfab,quietly=TRUE))
suppressPackageStartupMessages(library(testthat,quietly=TRUE))
suppressPackageStartupMessages(library(dplyr,quietly=TRUE))
suppressPackageStartupMessages(library(arrow,quietly=TRUE))
suppressPackageStartupMessages(library(hydrofabric,quietly=TRUE))
suppressPackageStartupMessages(library(data.table,quietly=TRUE))
# TODO establish a basic config file to read in for this functionality
comid <- "18094981"#"02479560"#14138870# A small basin
s3_base <- "s3://lynker-spatial/tabular-resources"
s3_bucket <- 'lynker-spatial'
s3_path_hydatl <- glue::glue('{s3_base}/hydroATLAS/hydroatlas_vars.parquet')

# Testing variables
ha_vars <- c('pet_mm_s01', 'cly_pc_sav', 'cly_pc_uav') # hydroatlas variables
usgs_vars <- c('TOT_TWI','TOT_PRSNOW','TOT_POPDENS90','TOT_EWT','TOT_RECHG')

# Define data directories to a package-specific data path
dir_base <- system.file("extdata",package="proc.attr.hydfab")
# Refer to temp_dir <- tempdir() in setup.R
temp_dir <- local_temp_dir() # If running this on your own, source 'setup.R' first.
dir_db_hydfab <- file.path(temp_dir,'hfab')
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
                                 dir_std_base = dir_user),
                    vars = list(usgs_vars = usgs_vars,
                                ha_vars = ha_vars),
                    datasets = 'xssa-mini',
                    xtra_hfab = list(hf_version = "2.1.1",
                                     hfab_retr = TRUE,
                                     type='nextgen',
                                     domain='conus'
                                     ))
# ---------------------------------------------------------------------------- #
#                              UNIT TESTING
# ---------------------------------------------------------------------------- #
testthat::test_that("proc_attr_std_hfsub_name standardized name generator", {
  testthat::expect_equal('hydrofab_testit_111.parquet',
               proc.attr.hydfab:::proc_attr_std_hfsub_name(111,"testit",'parquet'))

})

testthat::test_that("read_loc_data",{
  # Read in the normal gage
  good_file <- file.path(dir_base,"gage_id_example.csv")
  gage_dat <- proc.attr.hydfab::read_loc_data(loc_id_filepath = good_file,loc_id = 'gage_id',fmt='csv')
  testthat::expect_equal(ncol(gage_dat),1)
  testthat::expect_equal(colnames(gage_dat), 'gage_id')
  testthat::expect_true('character' %in% class(gage_dat$gage_id))
  testthat::expect_true(base::substring(gage_dat$gage_id[1],1,1)== "0")

  bad_file <- file.path(dir_base,"gage_id_ex_bad.parquet")
  bad_dat <- proc.attr.hydfab::read_loc_data(loc_id_filepath = bad_file,loc_id = 'gage_id', fmt = 'parquet')
  testthat::expect_true(base::substring(
    base::as.character(bad_dat$gage_id[1]),1,1)!="0")

})

testthat::test_that('proc_attr_gageids',{

  # test just usgs vars
  Retr_Params_usgs <- Retr_Params_ha <- Retr_Params
  Retr_Params_usgs$vars <- list(usgs_vars = usgs_vars)
  ls_comids <- proc.attr.hydfab::proc_attr_gageids(gage_ids=ls_fs_std$gage_ids[2],
                                      featureSource=ls_fs_std$featureSource,
                                      featureID=ls_fs_std$featureID,
                                      Retr_Params=Retr_Params_usgs,
                                      lyrs="network",overwrite=FALSE)
  testthat::expect_identical(names(ls_comids),ls_fs_std$gage_ids[2])
  testthat::expect_identical(class(ls_comids),"list")

  # test just hydroatlas var
  Retr_Params_ha$vars <- list(ha_vars = ha_vars)
  ls_comids_ha <- proc.attr.hydfab::proc_attr_gageids(gage_ids=ls_fs_std$gage_ids[2],
                                                   featureSource=ls_fs_std$featureSource,
                                                   featureID=ls_fs_std$featureID,
                                                   Retr_Params=Retr_Params_ha,
                                                   lyrs="network",overwrite=FALSE)

  # test a wrong featureSource
  testthat::expect_message(proc.attr.hydfab::proc_attr_gageids(gage_ids=ls_fs_std$gage_ids[2],
                                                   featureSource='notasource',
                                                   featureID=ls_fs_std$featureID,
                                                   Retr_Params=Retr_Params,
                                                   lyrs="network",overwrite=FALSE),
                           regexp="Skipping")
  # Expect 'skipping' this gage_id b/c NA doesn't exist
  testthat::expect_message(proc.attr.hydfab::proc_attr_gageids(gage_ids=c(NA),
                                                              featureSource='nwissite',
                                                              featureID=ls_fs_std$featureID,
                                                              Retr_Params=Retr_Params,
                                                              lyrs="network",overwrite=FALSE),
                           regexp="Skipping")

})

testthat::test_that('check_attr_selection', {
  ## Using a config yaml
  # Test for requesting something NOT in the attr menu
  attr_cfg_path_missing <- file.path(dir_base, 'xssa_attr_config_missing_vars.yaml')
  testthat::expect_message(testthat::expect_warning(expect_equal(proc.attr.hydfab::check_attr_selection(attr_cfg_path_missing), c("TOT_TWi", "TOT_POPDENS91"))))

  # Test for only requesting vars that ARE in the attr menu
  attr_cfg_path <- file.path(dir_base, '/xssa_attr_config_all_vars_avail.yaml')
  testthat::expect_message(testthat::expect_equal(proc.attr.hydfab::check_attr_selection(attr_cfg_path), NA))


  ## Using a list of variables of interest instead of a config yaml
  # Test for requesting something NOT in the attr menu
  vars <- c('TOT_TWi', 'TOT_PRSNOW', 'TOT_EWT')
  testthat::expect_warning(testthat::expect_equal(proc.attr.hydfab::check_attr_selection(vars = vars), 'TOT_TWi'))

  # Test for only requesting vars that ARE in the attr menu
  vars <- c('TOT_TWI', 'TOT_PRSNOW', 'TOT_EWT')
  testthat::expect_equal(proc.attr.hydfab::check_attr_selection(vars = vars), NA)
})


testthat::test_that('retrieve_attr_exst', {
  comids <- c("1520007","1623207","1638559","1722317") # !!Don't change this!!
  vars <- Retr_Params$vars %>% unlist() %>% unname()

  # Run tests based on expected dims
  dat_attr_all <- proc.attr.hydfab::retrieve_attr_exst(comids,vars,dir_db_attrs_pkg)
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
  nada_var <- testthat::capture_warning(proc.attr.hydfab::retrieve_attr_exst(comids,vars=c("TOT_TWI","naDa"),
                                              dir_db_attrs_pkg))
  testthat::expect_true(grepl("naDa",nada_var$message))
  nada_comid <- testthat::capture_condition(proc.attr.hydfab::retrieve_attr_exst(comids=c("1520007","1623207","nada"),vars,
                                              dir_db_attrs_pkg))
  testthat::expect_true(base::grepl("nada",nada_comid$message))

  testthat::expect_error(proc.attr.hydfab::retrieve_attr_exst(comids,vars=c(3134,3135),
                                            dir_db_attrs_pkg))
  testthat::expect_warning(proc.attr.hydfab::retrieve_attr_exst(comids=c(3134,3135),vars,
                                            dir_db_attrs_pkg))
})

# Read in data of expected format

testthat::test_that("proc_attr_wrap", {
  Retr_Params_all <- Retr_Params
  # Substitute w/ new tempdir based on setup.R
  Retr_Params$paths$dir_db_attrs <- Retr_Params$paths$dir_db_attrs %>%
                                    base::gsub(pattern=temp_dir,
                                               replacement=local_temp_dir2() )
  Retr_Params$paths$dir_db_hydfab <- Retr_Params$paths$dir_db_hydfab %>%
                                  base::gsub(pattern=temp_dir,
                                             replacement =local_temp_dir2() )
  Retr_Params_all$vars$ha_vars <- c("pet_mm_s01","cly_pc_sav")
  Retr_Params_all$vars$usgs_vars <-  c("TOT_TWI","TOT_PRSNOW","TOT_POPDENS90","TOT_EWT","TOT_RECHG","TOT_BFI")
  exp_dat <- readRDS(system.file("extdata", paste0("attrs_18094081.Rds"), package="proc.attr.hydfab"))
  exp_dat$attribute <- as.character(exp_dat$attribute)
  dat_all <- proc.attr.hydfab::proc_attr_wrap(comid=18094081,Retr_Params_all,
                                              lyrs='network',
                                              overwrite=TRUE )
  # How the exp_dat was originally created for unit testing
  # saveRDS(dat_all,paste0("~/git/fsds/pkg/proc.attr.hydfab/inst/extdata/attrs_18094081.Rds"))
  testthat::expect_true(dir.exists(dir_db_attrs))
  # Remove the dl_timestamp column for download timestamp and compare
  testthat::expect_equal(
    exp_dat %>% select(-dl_timestamp) %>% as.matrix(),
    dat_all %>% select(-dl_timestamp) %>% as.matrix())

  # Test when data exist in tempdir and new data do not exist
  Retr_Params_only_new <- Retr_Params
  Retr_Params_only_new$vars$usgs_vars <- c('TOT_PET')
  dat_add_pet <- suppressWarnings(proc.attr.hydfab::proc_attr_wrap(18094081,Retr_Params_only_new,
                                   lyrs='network',
                                   overwrite=FALSE ))
  testthat::expect_true(any('TOT_PET' %in% dat_add_pet$attribute))
  testthat::expect_true(any(grepl("TOT_PRSNOW", dat_add_pet$attribute)))

  # Test when some data exist in tempdir and new data needed
  Retr_Params_add <- Retr_Params
  # Sneak in the BFI variable
  Retr_Params_add$vars$usgs_vars <- c("TOT_TWI","TOT_PRSNOW","TOT_POPDENS90",
                                      "TOT_EWT","TOT_RECHG","TOT_BFI")
  dat_all_bfi <- suppressWarnings(proc.attr.hydfab::proc_attr_wrap(comid,
                                              Retr_Params_add,
                                              lyrs='network',
                                              overwrite=FALSE ))
  # Does the BFI var exist?
  testthat::expect_true(base::any('TOT_BFI' %in% dat_all_bfi$attribute))
  # testthat::expect_true(any(grepl("TOT_PRSNOW", dat_all_bfi$attribute)))


  # files_attrs <- file.path(Retr_Params$paths$dir_db_attrs,
  #                          list.files(Retr_Params$paths$dir_db_attrs))
  file.remove(file.path(Retr_Params$paths$dir_db_attrs,"comid_18094081_attrs.parquet"))
})

testthat::test_that("grab_attrs_datasets_fs_wrap", {

  ls_comids_all <- proc.attr.hydfab::grab_attrs_datasets_fs_wrap(Retr_Params,
                                                               lyrs="network",
                                                               overwrite=FALSE)
  testthat::expect_equal(names(ls_comids_all), Retr_Params$datasets)


  # Test wrong datasets name provided
  Retr_Params_bad_ds <- Retr_Params
  Retr_Params_bad_ds$datasets <- c("bad","xssa-mini")
  testthat::expect_error(
    proc.attr.hydfab::grab_attrs_datasets_fs_wrap(Retr_Params_bad_ds,
                                                    lyrs="network",
                                                    overwrite=FALSE))

  # Test that all datasets are processed
  Retr_Params_all_ds <- Retr_Params
  Retr_Params_all_ds$datasets <- "all"
  ls_comids_all_ds <- proc.attr.hydfab::grab_attrs_datasets_fs_wrap(Retr_Params_all_ds,
                                                                      lyrs="network",
                                                                      overwrite=FALSE)
  # When 'all' datasets requested, should have the same number retrieved
  testthat::expect_equal(length(ls_comids_all_ds),
                        length(list.files(Retr_Params_all_ds$paths$dir_std_base)))

  # Test running just the dataset path - not reading in a netcdf dataset.
  Retr_Params_no_ds <- Retr_Params
  Retr_Params_no_ds$datasets <- NULL
  good_file <- file.patRetr_Params_no_dsgood_file <- file.path(dir_base,"gage_id_example.csv")
  Retr_Params_no_ds$loc_id_read$loc_id_filepath <- good_file
  Retr_Params_no_ds$loc_id_read$gage_id <- 'gage_id'
  Retr_Params_no_ds$loc_id_read$featureSource_loc <- 'nwissite'
  Retr_Params_no_ds$loc_id_read$featureID_loc <- 'USGS-{gage_id}'
  Retr_Params_no_ds$loc_id_read$fmt <- 'csv'
  dat_gid_ex <- proc.attr.hydfab::grab_attrs_datasets_fs_wrap(Retr_Params_no_ds,
                                                  lyrs="network",
                                                  overwrite=FALSE)


})


testthat::test_that("proc_attr_hydatl", {
  exp_dat_ha <- readRDS(system.file("extdata", paste0("ha_18094981.Rds"), package="proc.attr.hydfab"))
  ha <- proc.attr.hydfab::proc_attr_hydatl(comid,s3_path_hydatl,
                                           ha_vars=c("pet_mm_s01","cly_pc_sav","cly_pc_uav"))
  # saveRDS(ha,paste0("~/git/fsds/pkg/proc.attr.hydfab/inst/extdata/ha_",comid,".Rds"))
  # Wide data expected
  testthat::expect_equal(ha,exp_dat_ha)

  # Run this with a bad s3 bucket
  testthat::expect_error(proc.attr.hydfab::proc_attr_hydatl(comid="18094981",
                                                          s3_path_hydatl ='https://s3.notabucket',
                                                          ha_vars = Retr_Params$vars$ha_vars))
})

testthat::test_that("proc_attr_usgs_nhd", {
  exp_dat <- readRDS(system.file("extdata", paste0("nhd_18094981.Rds"), package="proc.attr.hydfab"))
  order_cols <- c('COMID',"TOT_TWI","TOT_PRSNOW","TOT_POPDENS90","TOT_EWT","TOT_RECHG")
  usgs_meta <- proc.attr.hydfab::proc_attr_usgs_nhd(comid=18094981,
                   usgs_vars=c("TOT_TWI","TOT_PRSNOW","TOT_POPDENS90","TOT_EWT","TOT_RECHG")) %>%
                    data.table::setcolorder(order_cols)
  #saveRDS(usgs_meta,paste0("~/git/fsds/pkg/proc.attr.hydfab/inst/extdata/nhd_",comid,".Rds"))
  # Wide data expected
  # Check that the COMID col is returned (expected out of USGS data)
  testthat::expect_true(base::any(base::grepl("COMID",colnames(usgs_meta))))
  # Check for expected dataframe format
  testthat::expect_equal(usgs_meta,exp_dat)

})


testthat::test_that("proc_attr_hf not a comid",{
 testthat::expect_error(proc.attr.hydfab::proc_attr_hf(comid="13Notacomid14", dir_db_hydfab,
                                                       custom_name="{lyrs}_",fileext = 'gpkg',
                                                       lyrs=c('divides','network')[2],
                                                       hf_cat_sel=TRUE, overwrite=FALSE))
})

testthat::test_that("proc_attr_exst_wrap", {

  ls_rslt <- proc.attr.hydfab::proc_attr_exst_wrap(comid,
                                                   path_attrs=dir_db_attrs,
                                                   vars_ls=Retr_Params$vars,
                                                   bucket_conn=NA)
  testthat::expect_true(all(names(ls_rslt) == c("dt_all","need_vars")))
  testthat::expect_type(ls_rslt,'list')
  testthat::expect_s3_class(ls_rslt$dt_all,'data.table')
  testthat::expect_true(nrow(ls_rslt$dt_all)>0)

  # Testing for a comid that doesn't exist
  new_dir <- base::tempdir()
  ls_no_comid <- proc.attr.hydfab::proc_attr_exst_wrap(comid='notexist134',
                                                      path_attrs=file.path(new_dir,'newone','file.parquet'),
                                                      vars_ls=Retr_Params$vars,
                                                      bucket_conn=NA)
  testthat::expect_true(nrow(ls_no_comid$dt_all)==0)
  # Kinda-sorta running the test, but only useful if new_dir exists
  testthat::expect_equal(dir.exists(new_dir),
                         dir.exists(file.path(new_dir,'newone')))
})

testthat::test_that("hfab_config_opt",{
  config_in <- yaml::read_yaml(file.path(dir_base, 'xssa_attr_config_all_vars_avail.yaml'))
  reqd_hfab <- c("s3_base","s3_bucket","hf_cat_sel","source")
  hfab_config <- proc.attr.hydfab::hfab_config_opt(config_in$hydfab_config,
                                    reqd_hfab=reqd_hfab)

  testthat::expect_true(!base::any(reqd_hfab %in% names(hfab_config)))

  # A NULL hfab_retr is set to the default val in proc.attr.hydfab::proc_attr_wrap()
  hfab_cfg_edit <- config_in$hydfab_config
  names_cfg_edit <- lapply(hfab_cfg_edit, function(x) names(x)) %>% unlist()
  idx_hfab_retr <- grep("hfab_retr", names_cfg_edit)
  hfab_cfg_edit[[idx_hfab_retr]] <- list(hfab_retr = NULL)
  testthat::expect_identical(base::formals(proc.attr.hydfab::proc_attr_wrap)$hfab_retr,
                            proc.attr.hydfab::hfab_config_opt(hfab_cfg_edit,
                                                                reqd_hfab=reqd_hfab)$hfab_retr)
  # A NULL hf_version is set to the default val in proc_attr_wrap()
  hfab_cfg_hfsubsetr <- config_in$hydfab_config
  names_cfg_hfsubsetr <- lapply(hfab_cfg_hfsubsetr, function(x) names(x)) %>% unlist()
  idx_hfver <- grep("hf_version", names_cfg_hfsubsetr)
  hfab_cfg_hfsubsetr[[idx_hfver]] <- list(hf_version=NULL)

  testthat::expect_identical(base::formals(hfsubsetR::get_subset)$hf_version,
                             hfab_config_opt(hfab_cfg_hfsubsetr,
                                             reqd_hfab=reqd_hfab)$hf_version)

})
