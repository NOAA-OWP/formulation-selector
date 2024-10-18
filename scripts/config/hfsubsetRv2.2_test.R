library(hfsubsetR)
library(dplyr)
library(glue)
library(DBI)
library(tidyselect)
#comid <- c("6716129","7388043")
source <- "~/noaa/hydrofabric/v2.2/ls_conus.gpkg"
hf_ver <- '2.2'
#outfile <- glue::glue('~/noaa/hydrofabric/test/{comid}.gpkg')
dir_save <- '~/noaa/hydrofabric/test/'
hfab_vars <- "all"



weight_attrs_by_area <- function(df, hfab_vars, area_col = 'areasqkm'){
  #' @title summarize a multi-divide attribute dataset into area-weighted average attribute values
  #' @param df data.frame class. Attribute dataframe
  #' @param hfab_vars character class. The column names of attributes inside \code{df}
  #' @param area_col character class. The area column name inside \code{df}
  #' @return single-row data.frame of area-averaged attribute \code{df}
  #' @export
  tot_area <- base::sum(df[[area_col]])
  if(any(is.na(df))){ # Determine area-weighted mean, ignoring NA
    ls_wt_area <- list()
    for(hfvar in hfab_vars){
      prod_var_area <- df[[hfvar]]*df[[area_col]]
      if(any(is.na(prod_var_area))){
        idxs_na <- which(is.na(prod_var_area))
        sub_tot_area <- sum(df[[area_col]][-idxs_na]) # remove NA areas from consideration
        ls_wt_area[[hfvar]] <- sum(prod_var_area,na.rm = TRUE)/sub_tot_area
      } else {
        ls_wt_area[[hfvar]] <- sum(prod_var_area)/tot_area
      }
    }
  } else {
    ls_wt_area <- base::lapply(hfab_vars, function(a) try(base::sum(df[[a]]*df[[area_col]])/tot_area))
  }


  names(ls_wt_area) <- hfab_vars
  return(as.data.frame(ls_wt_area))
}

proc_attr_hfab <- function(comid,dir_save= "~/", hfab_vars="all",
                           attr_name = c("model-attributes","divide-attributes")[2],
                           div_name = "divides",
                           source="s3://lynker-spatial/hydrofabric", hf_ver = '2.2',
                           id_col = "divide_id", type = 'nextgen',
                           domain='conus'){
  #' @title Process hydrofabric attributes
  #' @description Connects to the hydrofabric via s3 or local connection and
  #' acquires attributes of interest
  #' @details If retrieved attribute data empty, generates warning.
  #' @param comid atomic
  #' @param dir_save The temporary directory location for saving subset hydrofabric.
  #' @param hfab_vars character vector. The attributes of interest to acquire
  #'  from hydrofabric. Default "all".
  #'  Refer to formulation-selector github wiki for options.
  #' @param attr_name The list name for attribute data as retrieved from
  #'  \code{hfsubsetR::get_subset()}. Default 'divide-attributes' corresponds to
  #'  hydrofabric v2.2. Previous versions used 'model-attributes'
  #' @param div_name The list name for the divides data as retrieved from
  #'  \code{hfsubsetR::get_subset()}. Default 'divides'.
  #' @param hf_ver Hydrofabric version. Default "2.2"
  #' @param id_col The identifier column for each divide inside the divides and
  #' divide-attributes layers. Default 'divide_id'
  #' @param type hydrofabric type, as used in \code{hfsubsetR::get_subset()}, default "nextgen"
  #' @param domain hydrofabric domain, as used in \code{hfsubsetR::get_subset()}, default "conus"
  #' @export

  lyrs <- c(attr_name, div_name)
  # TODO add local source check. Should this happen here or elsewhere?

  if (base::length(comid) > 1){
    stop("hfsubsetR only processes one comid at a time as of v0.0.9.
         If multi-comid processing becomes available, the
         weighted-area average calc needs to account for multiple
         comids")
  }

  if ((base::as.numeric(hf_ver)<2.2) && !('model-attributes' %in% lyrs)){
    warning("The geopackage layer 'model-attributes' was used prior to
            hydrofabric version 2.2 and may need to be defined in the `lyrs`
            argument of proc_attr_hfab() for use in hfsubsetR::get_subset().")
  }
  # -----------  READ HYDROFABRIC ATTRIBUTE DATA ------------ #
  # Read in the divide and divide-attributes layers
  if (tools::file_ext(source) == 'gpkg'){ # In case a local version of hydrofab exists
    outfile <- file.path(dir_save,glue::glue("hfab_attr_temp.gpkg"))
    rslt <- hfsubsetR::get_subset(
      gpkg = source,
      lyrs=lyrs,
      comid = comid[1],
      outfile = outfile,overwrite=TRUE)

    # Create a list of layers from the temporary location
    attr_div <- base::lapply(lyrs, function(l) sf::st_read(outfile, layer = l,quiet = TRUE))
    names(attr_div) <- lyrs

  } else { # Otherwise try the AWS connection
    attr_div <- hfsubsetR::get_subset(comid = comid,
                                          lyrs = lyrs,
                                          source   =source,
                                          hf_version =  hf_ver,
                                          type    = type,
                                          domain  =domain)
  }


  # -----------  SUBSET TO VARIABLES OF INTEREST ------------ #
  if (hfab_vars == 'all'){
    hfab_vars <- names(attr_div[[attr_name]])
    hfab_vars <- hfab_vars[-grep("vpuid", hfab_vars)]
    hfab_vars <- hfab_vars[-grep("divide_id", hfab_vars)]
  }
  attr_df <- attr_div[[attr_name]] %>%
    dplyr::select(dplyr::all_of(c("divide_id",hfab_vars))) %>%
    dplyr::select(-tidyselect::matches("vpuid"))

  if(nrow(attr_df) == 0){
    warning(glue::glue("COMID {comid} has no data in the hydrofabric. Skipping."))
  } else {
    # Combine model attributes with divides
    attrs_area <- dplyr::left_join(x=attr_df, attr_div[[div_name]], by="divide_id")

    if('dist_4.twi' %in% names(attrs_area)){
      #Expand dist_4.twi into multiple cols, by converting json format to df
      ls_dist_4_twi <- list()
      for(i in 1:nrow(attrs_area)){
        df_twi <- jsonlite::fromJSON(attrs_area[["dist_4.twi"]][[i]])

        ls_dist_4_twi[[i]] <- data.table::as.data.table(base::t(base::unlist(df_twi)))
      }
      df_twi_all <- data.table::rbindlist(ls_dist_4_twi,fill = TRUE) %>% base::as.data.frame()
      df_twi_sub  <- df_twi_all[,c("v1","v2","v3","v4")]
      new_twi_vars <- c("twi_25pctl", "twi_50pctl","twi_75pctl","twi_100pctl")
      names(df_twi_sub) <- new_twi_vars

      attrs_area <- base::cbind(attrs_area,df_twi_sub) %>%
        dplyr::select(-dplyr::all_of("dist_4.twi"))

      hfab_vars <- hfab_vars[-base::grep("dist_4.twi", hfab_vars)]
      hfab_vars <- c(hfab_vars,new_twi_vars)
    }

    if (base::length(base::unique(attr_div$divides$divide_id)) !=
        base::length(base::unique(attr_div[[attr_name]]$divide_id))){

      tot_area <- base::sum(attr_div[[div_name]]$areasqkm)
      attr_area <- base::sum(attrs_area$areasqkm)

      warning(glue::glue("COMID {comid} basin area totals {round(tot_area,2)}km^2,
                       but {attr_name} only cover {round(attr_area,2)}km^2"))
    }
    # -----------  AREAL WEIGHTING OF ATTRIBUTES ------------ #
    df_wt <- weight_attrs_by_area(df=attrs_area,hfab_vars=hfab_vars)
    df_wt$comid <- comid

    df_wt <- df_wt %>% dplyr::relocate(comid)
    return(df_wt)
  }
}



# Read in comids:
dir_attr <- "~/noaa/regionalization/data/input/attributes/"
files_attr <- list.files(dir_attr)
comids <- gsub("comid_","",files_attr) %>% gsub(pattern = "_attrs.parquet",replacement = "")



comids <- comids[grep("23864616",comids):length(comids)]

attr_dat <- list()
for(comid in comids){
  print(glue::glue("Processing {comid}"))
  rslt <- try(proc_attr_hfab(comid,dir_save=dir_save, hfab_vars="all",
                                      attr_name ="divide-attributes",
                                      div_name = "divides",
                                      source=source, hf_ver = '2.2',
                                      id_col = "divide_id", type = 'nextgen',
                                      domain='conus'))

  if("try-error" %in% rslt){ # sometimes trying again seems to fix things
    Sys.sleep(5)
    rslt <- try(proc_attr_hfab(comid,dir_save=dir_save, hfab_vars="all",
                               attr_name ="divide-attributes",
                               div_name = "divides",
                               source=source, hf_ver = '2.2',
                               id_col = "divide_id", type = 'nextgen',
                               domain='conus'))

  }

  if(!"try-error" %in% rslt){
    attr_dat[[comid]] <- rslt
  }
}



# Review all attribute data
check_empty_func <- function(x) {
  if (length(x) > 1) {
    return(x)
  }
}
sub_ls_attrs <- lapply(attr_dat, check_empty_func)

dt_all_attrs <- data.table::rbindlist(sub_ls_attrs)

summary(dt_all_attrs)

# TODO review all areas:
areas_all_ls <- list()
for(comid in comids){
  subset_dat <- hfsubsetR::get_subset(comid = comid,
                        lyrs = 'divides',
                        gpkg   =source,
                        hf_version =  hf_ver,
                        type    = type,
                        domain  =domain)
  areas_all_ls[[comid]] <- sum(subset_dat$divides$areasqkm)

}
library(ggplot2)
area_data <- unlist(unname(areas_all_ls)) %>% as.data.frame()
ggplot2::ggplot(area_data) +
  ggplot2::geom_histogram()

###### LOOKUP COMID LOCATION
library(nhdplusTools)

rslt <- nhdplusTools::get_nhdplus(comid="23864616",realization = 'outlet')
rslt$geometry
# Paste the coordinates into here: https://apps.nationalmap.gov/viewer/
  # TODO add divide id and attr areal coverages to final attribute dataset


#
#
#
# # Note that there are additional divide ids inside the divides layer, meaning the model-attributes layer is missing some divide ids
# print(glue::glue("Total divide ids inside divides layer: {length(unique(attr_div$divides$divide_id))}"))
# print(glue::glue("Total divide ids inside model-attributes layer: {length(unique(attr_div$`model-attributes`$divide_id))}"))
#
# # Total area accounted for in each layer:
# print(glue::glue("Total catchment area inside the divides layer: {sum(attr_div$divides$areasqkm)} km^2"))
#
# print(glue::glue("Total catchment area inside the model-attributes layer: {sum(attrs_area$areasqkm)} km^2"))
#
# ######
#
# # https://noaa-owp.github.io/hydrofabric/articles/05-subsetting.html
# library(dplyr)
# library(arrow)
# library(hydrofabric)
# proc_attr_hfab <- function(comid,usgs_vars){
#
#
# }
# (g = open_dataset('s3://lynker-spatial/hydrofabric/v2.2/conus_hl') |>
#     select("vpuid", 'hl_reference', "hl_link") %>%
#     filter(hl_link == '06752260') %>%
#     collect())
#
# dat <- arrow::read_parquet("/Users/guylitt/Downloads/nextgen_04.parquet")
#
# dim(dat)
#
# (hydLoc <- hfsubsetR::findOrigin(network_path, comid=comid))
#
# attr_data <- arrow::open_dataset("s3://lynker-spatial/hydrofabric/v2.1.1/nextgen/conus_model-attributes") |>
#   filter(vpuid == hydLoc$vpuid) |>
#   # filter(divide_id==hydLoc$id) |>
#   collect()
#
#
# s3      <- "s3://lynker-spatial/hydrofabric"
# version <-  'v2.1.1'
# type    <- "nextgen"
# domain  <- "conus"
# network_path <- glue("{s3}/{version}/{type}/conus_network")
# net <- open_dataset(network_path)
#
# glimpse(filter(net,hl_uri == "HUC12-010100100101"))
#
# subset_enhanced = get_subset(comid = comid,
#                              lyrs = c("model-attributes","divides")
#                              #lyrs = c("forcing-weights", "model-attributes","divides","nexus"),
#                              source   =s3,
#                              hf_version =  '2.1.1',
#                              type    = "nextgen",
#                              domain  = "conus")
# length(unique(subset_enhanced$`model-attributes`$divide_id))
# length(unique(subset_enhanced$divides$divide_id))
#
# intersect(subset_enhanced$`model-attributes`$divide_id,subset_enhanced$divides$divide_id)
#
# attrs_area <- dplyr::left_join(x=subset_enhanced$`model-attributes`, subset_enhanced$divides, by="divide_id")
# # TODO why does the total area differ for comid "6716129"? Some divide_ids do not have attributes calculated (~10% of total catchment area)
# (totl_actl_area <- sum(subset_enhanced$divides$areasqkm))
# tot_area <- sum(attrs_area$areasqkm)
# gwCoefWt <- sum(attrs_area$gw_Coeff*attrs_area$areasqkm)/tot_area
# sum(attrs_area$impervious_mean*attrs_area$areasqkm)/tot_area
#
# merge(subset_enhanced)
#
# subset_enhanced$divides %>% filter(divide_id %in% subset_enhanced$`model-attributes`$divide_id)
#
# length(subset_enhanced$`forcing-weights`$)
# subset_enhanced$divides
#
#
#
#
#

library(nhdplusTools)
nldi_feat <- list()
nhdplusTools::discover_nhdplus_id()
