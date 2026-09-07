#' @title Script to work through FY25 NWM v4 benchmarking locations (first stage, small # of catchments)
#' @description GOAL: Identify
#' @seealso prep_oconus_hydroatlas.R for preparation of hydroatlas attributes
#' corresponding to AK and PRVI hydrofabric VPU domains.

# Benchmarking exercises:
library(proc.attr.hydfab)
library(janitor)
library(readr)
library(hydrofabric)
library(hfsubsetR)
library(maps)
library(mapdata)

# Function to get state name



# Example usage
# lat <- 41.8781
# lon <- -87.6298
# usvi <- c(17.725496,-64.845511)
# pr <- c(-66.992208,18.122422,4326)
# lon <- pr[1]
# lat <- pr[2]
# lon <- usvi[2]
# lat <- usvi[1]
# get_state_or_territory(pr[2],pr[1])
# state_name <- get_state_or_territory(latitude, longitude)
#
# print(state_name)
path_oconus_hfab_config <- "~/git/rafts/scripts/workflow_configs/legacy/bm_test25/bm_oconus_config.yaml"
path_nwps_rpt  <- 'https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv'
path_hads_sites <- 'https://hads.ncep.noaa.gov/USGS/ALL_USGS-HADS_SITES.txt'
path_nwps_api <- "https://api.water.noaa.gov/nwps/v1/gauges"

gauge_ids <- c("JOPM7","RNDO2","CSNC2",
               "UCHA2","TYAA2","WLWA2",
               "ALEC2","BERU1","OAKA3",
               "CREC1","HPIC1","PRBC1",
               "WDVA1","BDCL1","PLAM6",
               "CRTN6","FDKM2","LODN4",
               "BLRM7","DUBW4","PGEN8",
               "KALI4","HWYM5","HHTM4",
               "NRWM3","CENV1","CHRN6",
               "FSSO3","DRSW1","WGCM8",
               "DLYW2","DEPI3","LARO1",
               "VDSG1","CATA1","MKHF1",
               "KLGT2","ATIT2","SDAT2",
               "COMP4","MOCP4","NGKP4",
               "HLEH1","WLUH1","WHSH1")

data_source <- c("nwps","hads")[2] # Recommended to use HADS over NWPS
# ----- grab comids using a method proposed by Mike Johnson

#### NWPS data
# NOTE: NWPS gauges not comprehensive
if(data_source == "nwps"){
  d_nwps <- proc.attr.hydfab::read_noaa_nwps_gauges(
    path_nwps_rpt =path_nwps_rpt)

  d_nwps_sub <- base::lapply(gauge_ids,
                             function(gid) dplyr::filter(d_nwps, nws_shef_id == gid)) %>%
    data.table::rbindlist()
  d_nwps_sub <- d_nwps_sub %>% sf::st_as_sf(coords = c('longitude', 'latitude'), crs = 4326)

  comids_nwps <- proc.attr.hydfab::retr_comids_coords(df=d_nwps_sub, col_lat ='latitude',
                                                 col_lon='longitude',crs=4326)
  d_nwps_sub$comid <- comids_nwps
  dt_sub <- data.table::data.table(d_nwps_sub)
} else if(data_source == 'hads'){
  #### HADS DATA RETRIEVAL/FILTERING
  # NOTE: HADS data are comprehensive. Read all data.
  dt_hads <- proc.attr.hydfab::read_noaa_hads_sites(
    path_hads_sites=path_hads_sites)

  # Subset HADS to NOAA gauge_ids of interest
  dt_hads_sub <- base::lapply(gauge_ids,
                              function(gid) dt_hads %>% dplyr::filter(lid==gid)) %>%
    data.table::rbindlist()

  comids_hads <- proc.attr.hydfab::retr_comids_coords(df=dt_hads_sub, col_lat ='latitude',
                                                      col_lon='longitude',col_crs='crs')

  if(base::all(base::is.na(comids_hads))){
    warning("POTENTIAL PROBLEM WITH nhdplusTools::discover_nhdplus_id():
    No comids returned. This may relate to database connection limits or a bad connection.")

    # Now try to acquire comids via USGS gage Ids
    comids_hads <- base::lapply(dt_hads_sub$usgsId,function(gid)
      nhdplusTools::discover_nhdplus_id(nldi_feature =
                                      base::c(featureSource='nwissite',
                                              featureID=paste0("USGS-",gid))))
    if(base::any(!base::is.na(comids_hads))){
      base::message("comids successfully discovered using USGS gage IDs")
    }
  }
  dt_hads_sub$comid <- comids_hads
  dt_sub <-dt_hads_sub
}

write.csv("/")

# Populate standardized featureID and featureSource unique identifiers
dt_meta <- proc.attr.hydfab::std_feat_id(df=dt_sub,
                                        name_featureSource ="COMID",
                                        col_featureID = 'comid')


# ################### SEARCH FOR MISSING HYDROFABRIC IDS #######################
if (base::any(base::is.na(dt_meta$featureID))){
  dt_need_hf <- dt_meta[base::which(base::is.na(dt_meta$featureID)),]

  # TODO may modify this given the updated hydrofabric per https://github.com/owp-spatial/hfsubsetR/issues/6
  # Retrieve the hydrofabric IDs wrapper for needed locations
  dt_have_hf <- proc.attr.hydfab::retr_hfab_id_wrap(dt_need_hf,
                                    path_oconus_hfab_config,
                                    col_usgsId = 'usgsId',col_lon= 'longitude',
                                    col_lat= 'latitude',epsg_coords=4326)

  # Subset to the new columns of interest (plus the common ID column usgsId)
  sub_dt_have_hf <- dt_have_hf %>% dplyr::select(c("usgsId",featureID, featureSource))

  # Fill in the missing NA values for featureID and featureSource columns
  dt_meta <- dt_meta %>% dplyr::left_join(sub_dt_have_hf, by = "usgsId",
                                                    suffix=c("_df1","_df2")) %>%
    dplyr::mutate(featureID = ifelse(is.na(featureID_df1),featureID_df2, featureID_df1),
                  featureSource = ifelse(is.na(featureSource_df1),featureID_df2, featureID_df1)
    ) %>%
    dplyr::select(-dplyr::all_of(
      base::c("featureID_df1",'featureID_df2',
              'featureSource_df1','featureSource_df2')))
}
########################## CATCHMENT ATTRIBUTES ################################
# Now that we have the unique IDs, we can retrieve the catchment attributes

# Known hydroatlas references:
# https://github.com/NOAA-OWP/hydrofabric/wiki/Data-Access-Patterns

library(arrow)
# hydatl <- arrow::read_parquet("~/Downloads/hydroatlas_vars.parquet")
# TODO retrieve hydroatlas catchment attributes (make them a parquet format)

# tabular data:
dir_hfab_tab_dat <- "~/noaa/hydrofabric/tabular-data/" # Save the parquet file here
path_attrs_all_oconus <- proc.attr.hydfab:::std_path_attrs_all_parq(dir_hfab_tab_dat, ls_vpus=c("ak","prvi"))
path_attrs_conus <- file.path(dir_hfab_tab_dat,"hydroatlas_vars.parquet")
#path_attrs_all_oconus <- "~/noaa/hydrofabric/tabular-data//hydroatlas_attributes_ak_prvi.parquet"


# ---------------------------------------------------------------------------- #
#. Trying to formalize here
# ---------------------------------------------------------------------------- #
path_attr_config <- "~/git/rafts/scripts/workflow_configs/legacy/xssa/xssa_attr_config.yaml"

Retr_Params <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)

# TODO update function that creates Retr_Params: add hydroatlas paths to Retr_Params$paths
Retr_Params$paths$dir_hfab_tab_dat <- dir_hfab_tab_dat # TODO define path in attr_config
Retr_Params$paths$path_attrs_conus <- path_attrs_conus # TODO define path in attr_config
Retr_Params$paths$path_attrs_all_oconus <- proc.attr.hydfab:::std_path_attrs_all_parq(dir_hfab_tab_dat, ls_vpus=c("ak","prvi")) # TODO define ls_vpus in attr_config

# TODO generate hf_id using proc.attr.hydfab::custom_hf_id(dt_ha_oc, col_vpu = "vpu",col_id = "id")

# Example of retrieving a .nc standardized dataset following rafts_proc
ds <- Retr_Params$datasets[1]
ls_rafts_std <- proc.attr.hydfab::proc_attr_read_gage_ids_fs( proc.attr.hydfab::std_dir_dataset(Retr_Params$paths$dir_std_base,ds))
# PROBLEM: this assumes every gage_ids uses the same featureSource
# WORKAROUND: make a list of networks using standardized options e.g.
# TODO implement a standardization of hydrofabric ids in the rafts_proc Step 1 approach.
# Idea: Generate a separate .nc file for hydrofabric formatting & separate for nhdplus fomratting
# Idea: Generate a separate

ls_rafts_std_ntwk <- list()
# TODO determine how to split up data between network options:
# 1) conus vs. 2) oconus?
# 2) networks: 1) nhdplus (aka conus) vs 2) hydrofabric (oconus) vs 3) HydroATLAS networks (global)
# What are acceptable location identifiers?
#. 1) RFC IDs : convert to hydrofabric id
#. 2) USGS gage ids : convert to hydrofabric id (or comid??)
#. 3) coordinates
#. 4) hydrofabric location ids

ls_rafts_std_ntwk[['nhdplus']] <- ls_rafts_std # valid with historic versions of proc.attr.hydfab, specific to NHDPlus comid locations
ls_rafts_std_ntwk[['hydrofabric']] <- list(loc_id = c('ak-wb-10272','prvi-wb-'), # TODO how to handle coordinate searches??
                                        col_uid = c('hf_uid','hf_uid'), # TODO how to handle coordinate searches??
                                        path_dat_in = "TODO") # hydrofabric compatibility for OCONUS-relevant IDs





# TODO add in some $g


proc.attr.hydfab::retr_attr_hydatl(hf_id = 899,path_ha = path_attrs_conus,ha_vars=Retr_Params$vars$ha_vars)

# ---------------------------------------------------------------------------- #
proc.attr.hydfab::retr_attr_hydatl(hf_id = 899,path_ha = path_attrs_conus,ha_vars =c("ari_ix_sav","cly_pc_sav","snw_pc_uyr"))
proc.attr.hydfab::retr_attr_hydatl(hf_id = "ak-wb-10272", path_ha = path_attrs_all_oconus,ha_vars =c("ari_ix_sav","cly_pc_sav","snw_pc_uyr"))

paths_ha <- c(path_attrs_conus, path_attrs_all_oconus)
hf_id_cols = c("hf_uid",'hfab_uid',"hf_id", "id") # TODO remove hfab_id

hf_id_col <- "id"

dt_ha_oc <- arrow::read_parquet(path_attrs_all_oconus)

# TODO perform clean up on oconus NA values and remake hf_uid.
idxs_na_id <- which(is.na(dt_ha_oc$id))
dt_ha_oc$id[idxs_na_id] <- base::gsub(pattern = "cat-",replacement= "wb-",
                                      x = dt_ha_oc$divide_id[idxs_na_id])
dt_ha_oc$hf_uid <- proc.attr.hydfab::custom_hf_id(dt_ha_oc, col_vpu = "vpu",col_id = "id")

length(which(is.na(dt_ha_oc$id)))

length(unique(dt_ha_oc$hfab_uid))

head(dt_ha_oc$id)
hf_id <- "wb-16439"
hf_id <- c("wb-8982","wb-16439", "wb-10272")
ha_vars <- c("ari_ix_sav","cly_pc_sav","snw_pc_uyr")


ha <- arrow::open_dataset(path_attrs_all_oconus) %>%
  dplyr::filter(!!dplyr::sym(hf_id_col) %in% hf_id) %>%#
  dplyr::select(hf_id_col, dplyr::all_of(ha_vars)) %>%
  dplyr::collect()

# Now grab attributes for these watersheds
path_attr_config <- "~/git/rafts/scripts/analysis/benchmarking/oconus_attrs.yaml"
Retr_Params <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)


# TODO determine vpu to map to appropriate hydrofabric geopackage created by

# TODO add

proc.attr.hydfab::rafts_attrs_miss_mlti_wrap(path_attr_config)


#%%
# PROCESS ATTRIBUTES
dt_comids <- proc.attr.hydfab:::grab_attrs_datasets_rafts_wrap(Retr_Params,overwrite = FALSE)

# --------------------------- Compile attributes --------------------------- #
# Demonstration of how to retrieve attributes/comids that exist inside dir_db_attrs:
demo_example <- FALSE
if (demo_example){
  # The comids of interest
  comids <- dt_comids$featureID %>% base::unname() %>% base::unlist()

  # The attribute variables of interest
  vars <- Retr_Params$vars %>% base::unlist() %>% base::unname()

  dat_all_attrs <- proc.attr.hydfab::retrieve_attr_exst(comids, vars,
                                                        Retr_Params$paths$dir_db_attrs)
  base::rm(dat_all_attrs)

}


#
# # -----
# testing_nwps_api = FALSE
# if(testing_nwps_api){
#   dt_meta_noaa <- proc.attr.hydfab::retr_noaa_gauges_meta(gauge_ids =gauge_ids,
#                                                           gauge_url_base = path_nwps_api,
#                                                           retr_ids = c("lid","usgsId","name","latitude","longitude"))
#
#   dt_meta_noaa_sub_no_coords <- dt_meta_noaa[base::which(is.na(dt_meta_noaa$latitude)),]
#
#   dt_hads_has_sub <- base::lapply(dt_meta_noaa_sub_no_coords$lid,
#                                   function(id) dt_hads %>% dplyr::filter(lid == id)) %>%
#     data.table::rbindlist()
#   if(base::any(base::is.na(dret_meta_noaa$latitude))){
#
#   }
#
#   # for some reason, CSNC2 is not detected in the database. USGS-07103700
#   dt_meta_noaa[['usgsId']][dt_meta_noaa$lid == "CSNC2"] <- "07103700"
#   dt_meta_noaa[['name']][dt_meta_noaa$lid == "CSNC2"] <- "Fountain Creek Near Colorado Springs CO"
#
#
#   # Populate standardized featureID and featureSource unique identifiers
#   dt_meta_noaa <- proc.attr.hydfab::std_feat_id(df=dt_meta_noaa,
#                                                 name_featureSource ="COMID",
#                                                 vals_featureID = comids)
#
#
#   # -----------------
#   library(httr)
#   library(jsonlite)
#   retr_all_nwps_gauges <- function(gauge_url_base="https://api.water.noaa.gov/nwps/v1/gauges"){
#     resp <- httr::GET(gauge_url_base)
#     if(status_code(resp) == 200){
#       contents <- httr::content(resp, as='text',encoding= "UTF-8")
#       ls_nwps_gages <- jsonlite::fromJSON(contents,flatten=TRUE)
#       df <- as.data.frame(data_list)
#     }
#   }
#
# }
#
#
#
# # -----
# # TODO build this map based on config file rather than hard-code it
# # Mapping the geopackage file locations to their postal id & expected CRS
# # hfab_srce_map <- data.table::data.table(domain = c("AK","PR","VI","HI"),
# #            paths = c("~/noaa/hydrofabric/v2.2/ak_nextgen.gpkg",
# #                      "~/noaa/hydrofabric/v2.2/prvi_nextgen.gpkg",
# #                      "~/noaa/hydrofabric/v2.2/prvi_nextgen.gpkg",
# #                      "~/noaa/hydrofabric/v2.2/hi_nextgen.gpkg"),
# #            crs_epsg = c("EPSG:3338","EPSG:6566",
# #                         "EPSG:6566","ESRI:102007") # just in case can't be automatically detected with sf
# #            )
#
#
#
# # df <- arrow::read_parquet("~/noaa/regionalization/data/input/attributes/comid_10023916_attrs.parquet")
#


#
