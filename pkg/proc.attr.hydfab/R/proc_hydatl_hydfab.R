
library(sf)
library(logr)
library(ggplot2)

#' @title Collection of functions for processing hydrofabric data with HydroATLAS data
#' @description These are not fully formalized functions! Serving a quick-and-dirty
#' geospatial processing need that maps HydroATLAS attributes to OCONUS
#' hydrofabrics locations across AK and PR
#' @details Functions that are internal to proc.attr.hydfab,
#' not intended for general use
#' intended to run very infrequently - only when HydroATLAS or hydrofabric datasets change
#' @seealso proc.attr.hydfab/flow/prep_oconus_hydroatlas.R, the script that calls these functions

# Changelog / Contributions
# 2025 Spring originally created, GL
# 2025-08-14 Added logr, GL

read_hydatl_by_vpu_val <- function(vpu,dir_base_hydatl){
  #' @title Read the HydroATLAS by vpu value
  #' @description Define Paths to HydroATLAS data downloaded from HydroATLAS website
  #'  based on the hydrofabric vpu identifiers. Make geometries valid.
  #' @param vpu The OCONUS VPU id used in the hydrofabric. Options
  if(vpu=="ak"){
    # Read in the arctic HydroATLAS data
    path_hab_shp <- file.path(dir_base_hydatl,"hybas_ar_lev01-12_v1c","hybas_ar_lev12_v1c.shp")
  } else if (vpu=="prvi"){
    # Read in the north america HydroATLAS data
    path_hab_shp <- file.path(dir_base_hydatl,"hybas_na_lev01-12_v1c","hybas_na_lev12_v1c.shp")
  } else {
    logr::log_print("Problem: vpu not identified.",level="ERROR")
    stop()
  }
  if(!file.exists(path_hab_shp)){
    stop_msg <- glue::glue("MUST download the HydroATLAS basin dataset for {vpu} from
    https://www.hydrosheds.org/products/hydrobasins for the Arctic & North America
    and place inside {dir_base_hydatl}")
    logr::log_print(stop_msg,level="ERROR")
    stop()
  }

  logr::log_(glue::glue("Reading, making valid {path_hab_shp} for {vpu} vpu."),
             level="INFO")
  hab_shp <- sf::read_sf(path_hab_shp)
  # Make the geometries valid
  hab_shp_val <- sf::st_make_valid(hab_shp)

  return(hab_shp_val)
}

subset_hydatl_by_hydfab <- function(div_hfab_val,hab_shp_val,
                                    buff_dist = 50000){
  #' @title Subset the HydroATLAS data to a buffered hydrofabric extent
  #' @param div_hfab_val validated hydrofabric divides of interest.
  #' Presumed to be the smaller spatial extent, sf object
  #' @param hab_shp_val validated HydroATLAS basin.
  #' Presumed to be the larger spatial extent, sf object
  #' @param buff_dist The distance for a buffer around the hydrofabric to ensure
  #' full HydroATLAS coverage
  extent_hfab <- sf::st_bbox(div_hfab_val)
  extent_hfab_sf <- st_as_sfc(extent_hfab)
  extent_hfab_buff <- sf::st_buffer(extent_hfab_sf, dist = buff_dist)
  hab_shp_sub <- sf::st_intersection(hab_shp_val, extent_hfab_buff)
  return(hab_shp_sub)
}

std_paths_ntrsct <- function(path_hfab){
  #' @title Standardizing the paths to hydrofabric-HydroATLAS intersection data
  new_file_name <- base::gsub(pattern = ".gpkg",replacement="_all.rds",
                              x = base::basename(path_hfab))
  path_save_ls_ntrsct <- base::file.path(dir_save_base,new_file_name)
  path_save_ntrsct_gpkg <- gsub(pattern=".rds",replacement=".gpkg",
                                path_save_ls_ntrsct)

  return(list(rds=path_save_ls_ntrsct, gpkg = path_save_ntrsct_gpkg))
}

std_paths_ha_attrs <- function(dir_base_hfab, vpu){
  #' @title standardize path to the HydroATLAS attributes corresponding to
  #' each hydrofabric divide, saved as a csv
  #' @param dir_base_hfab Base directory where hydrofabric data stored
  #' @param vpu the hydrofabric vpu of interest (e.g. `'ak'` or `'prvi'`)
  # Changelog/contributions
  # 2025-03 originally created, GL
  # 2025-05-08 rename from std_paths_attrs to std_paths_ha_attrs
  path_attrs_new <- base::file.path(dir_base_hfab,
                            base::paste0(vpu,"_hydroatlas_attrs.csv"))
  return(path_attrs_new)
}

std_path_attrs_all_parq <- function(dir_base_hfab,ls_vpus=c("ak","prvi")){
  #' @title standardize path to the HydroATLAS attributes for all OCONUS
  #' hydrofabric domains
  #' @details Intended for just ak and prvi
  #' @param dir_base_hfab Base directory where hydrofabric data stored
  #' @param ls_vpu the hydrofabric vpus of interest (e.g. `c('ak','prvi')`)
  #' @export
  all_vpus <- base::paste0(base::sort(ls_vpus),collapse = "_")
  path_attrs <- base::file.path(dir_base_hfab,
                                glue::glue("hydroatlas_attributes_{all_vpus}.parquet"))
  return(path_attrs)
}


read_hfab_lyr_val <- function(path_hfab, lyr = 'divides'){
  #' @title Read the hydrofabric layer, convert to WGS 84, and make valid
  #' @param path_hfab filepath to the hydrofabric geopackage of interest
  #' @param lyr The layer to read from the geopackage, default `'divides'`
  logr::log_print(glue::glue("Reading, transforming, & make valid {path_hfab}"),
                  leve="INFO")
  div_hfab <- sf::st_read(path_hfab,layer = lyr,quiet=TRUE) # e.g. EPSG: 3338
  div_hfab_tfrm <- sf::st_transform(div_hfab, crs = 4326) # convert to 4326
  div_hfab_val <- sf::st_make_valid(div_hfab_tfrm)
  return(div_hfab_val)
}

plot_hf_ha <- function(div_hf_hab, viz_idx=1, total_vpu=FALSE,
                       col_geom_ha='geometry',
                       col_geom_hf='geom',
                       col_centroid_hf='centroid'){
  #' @title Plot hydrofabric and HydroATLAS basins
  #' @details Will calculate hydrofabric centroids if column doesn't exist
  #' @param div_hf_hab merged dataframe of hydrofabric and HydroATLAS
  #' @param viz_idx Row indices of dataframe for plotting. Default 1.
  #' @param total_vpu Boolean. Should the entire dataframe's gemoetry also be included?

  map_basins <- ggplot2::ggplot()
  if(total_vpu){ # View the entire vpu/domain
    map_basins <- map_basins + ggplot2::geom_sf(data = div_hf_hab$geometry)
  }
  if(!col_centroid_hf %in% names(div_hf_hab)){ # Compute the
    div_hf_hfab[[col_centroid_hf]] <- sf::st_centroid(div_hf_hfab[[col_geom_hf]])
  }

  map_basins <- map_basins +
    ggplot2::ggtitle(glue::glue("domain: {vpu}\nid:{div_hf_hab$id[viz_idx]} divide_id:{div_hf_hab$divide_id[viz_idx]}\nHYBAS_ID:{div_hf_hab$HYBAS_ID[viz_idx]}")) +
    ggplot2::geom_sf(data = div_hf_hab[viz_idx,col_geom_ha], ggplot2::aes(color = "HydroAtlas")) +
    ggplot2::geom_sf(data = div_hf_hab[viz_idx,col_geom_hf], ggplot2::aes(color = 'hydrofabric'), alpha=0.3) +
    ggplot2::geom_sf(data = div_hf_hab[viz_idx,col_centroid_hf], ggplot2::aes(color = 'hf centroid')) +
    ggplot2::ggtitle(glue::glue("domain: {vpu}\nid:{div_hf_hab$id[viz_idx]} divide_id:{div_hf_hab$divide_id[viz_idx]}\nHYBAS_ID:{div_hf_hab$HYBAS_ID[viz_idx]}")) +
    ggplot2::scale_color_manual(name="Layers",
                                values = c("HydroAtlas"='green',
                                           'hydrofabric'='blue',
                                           'hf centroid'='blue'))
  return(map_basins)
}
