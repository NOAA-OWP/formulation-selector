#' @title Graveyard for deprecated functions. Zombies still a possibility.
proc_attr_wrap <- function(comid, Retr_Params, lyrs='network',overwrite=FALSE,hfab_retr=FALSE){
  #' @title DEPRECATED. Wrapper to retrieve variables when processing attributes
  #' @author Guy Litt \email{guy.litt@noaa.gov}
  #' @description DEPRECATED. Use [proc_attr_mlti_wrap] instead.
  #' Identifies a single comid location using the hydrofabric and then
  #' acquires user-requested variables from multiple sources. Writes all
  #' acquired variables to a parquet file as a standard data.table format.
  #' Re-processing runs only download data that have not yet been acquired.
  #' @details Function returns & writes a data.table of all these fields:
  #'   featureID - e.g. USGS common identifier (default)
  #'   featureSource - e.g. "COMID" (default)
  #'   data_source - where the data came from (e.g. 'usgs_nhdplus__v2','hydroatlas__v1')
  #'   dl_timestamp - timestamp of when data were downloaded
  #'   attribute - the variable identifier used in a particular dataset
  #'   value - the value of the identifier
  #' @param comid character. The common identifier USGS location code for a surface water feature.
  #' @param Retr_Params list. List of list structure with parameters/paths needed to acquire variables of interest
  #' @param lyrs character. The layer names of interest from the hydrofabric gpkg. Default 'network'
  #' @param overwrite boolean. Should the hydrofabric cloud data acquisition be redone and overwrite any local files? Default FALSE.
  #' @param hfab_retr boolean. Should the hydrofabric geopackage data be retrieved? Default FALSE.
  #' @seealso \link[proc.attr.hydfab]{hfab_config_opt} Searches for default arguments from this function using formals
  #' @seealso \link[proc.attr.hydfab]{proc_attrs_gageids} Also references this function's default args using formals
  #' @seealso \link[proc.attr.hydfab]{proc_attr_mlti_wrap}
  #' @export

  # Changelog / Contributions
  #   2024-07-25 Originally created, GL
  message(base::paste0("Processing COMID ",comid))

  if(hfab_retr){ # Retreive the hydrofabric data, downloading to dir_db_hydfab
    # Retrieve the hydrofabric id
    # TODO proc_attr_hf doesn't work as expected. Consider overhaul
    net <- try(proc.attr.hydfab::proc_attr_hf(comid=comid,
                                              dir_db_hydfab=Retr_Params$paths$dir_db_hydfab,
                                              custom_name ="{lyrs}_",
                                              lyrs=Retr_Params$xtra_hfab$lyrs,
                                              hf_version = Retr_Params$xtra_hfab$hf_version,
                                              type = Retr_Params$xtra_hfab$type,
                                              domain = Retr_Params$xtra_hfab$domain,
                                              overwrite=overwrite))
    if ('try-error' %in% base::class(net)){
      warning(glue::glue("Could not acquire hydrofabric for comid {comid}. Proceeding to acquire variables of interest without hydrofabric."))
      net <- list()
      net$hf_id <- comid
    }
  } else {
    net <- list()
    net$hf_id <- comid
  }

  # Define the path to the attribute parquet file (name contains comid)
  path_attrs <- proc.attr.hydfab::std_path_attrs(comid=net$hf_id,
                                                 dir_db_attrs=Retr_Params$paths$dir_db_attrs)

  vars_ls <- Retr_Params$vars
  # ------- Retr_Params$vars format checker --------- #
  # Run check on requested variables for retrieval:
  proc.attr.hydfab:::wrap_check_vars(vars_ls)

  # ----------- existing dataset checker ----------- #
  ls_chck <- proc.attr.hydfab::proc_attr_exst_wrap(comid,path_attrs,
                                                   vars_ls,bucket_conn=NA)
  dt_all <- ls_chck$dt_all
  need_vars <- ls_chck$need_vars_ls

  # --------------- dataset grabber ---------------- #
  attr_data <- proc.attr.hydfab::retr_attr_new(locids=net$hf_id,need_vars=need_vars,
                                               paths_ha=Retr_Params$paths$paths_ha)

  # Combine freshly-acquired data
  dt_new_dat <- data.table::rbindlist(attr_data,use.names=TRUE,fill=TRUE)
  #dt_new_dat <- data.table::rbindlist(attr_data_ls)

  # Combined dt of existing data and newly acquired data
  if(base::dim(dt_all)[1]>0 && base::dim(dt_new_dat)[1]>0){
    dt_cmbo <- data.table::merge.data.table(dt_all,dt_new_dat,
                                            all=TRUE,no.dups=TRUE)
  } else if (base::dim(dt_new_dat)[1] >0){
    dt_cmbo <- dt_new_dat
  } else {
    dt_cmbo <- dt_all
  }
  # Remove all factors to make arrow::open_dataset() easier to work with
  dt_cmbo <- dt_cmbo %>% dplyr::mutate(across(where(is.factor), as.character))

  # Write attribute variable data specific to a comid here
  arrow::write_parquet(dt_cmbo,path_attrs)
  return(dt_cmbo)
}



proc_attr_hf <- function(comid, dir_db_hydfab,custom_name="{lyrs}_",fileext = 'gpkg',
                         lyrs=c('divides','network')[2],
                         hf_cat_sel=TRUE,
                         overwrite=FALSE,
                         hf_version = NULL,
                         type = NULL,
                         domain = NULL
){

  #' @title DEPRECATED. Retrieve hydrofabric data of interest based on location identifier
  #' @author Guy Litt \email{guy.litt@noaa.gov}
  #' @description Checks to see if a local dataset exists. If not, retrieve from lynker-spatial s3 bucket
  #' @param comid character class. The common identifier USGS location code for a surface water feature.
  #' @param dir_db_hydfab character class. Local directory path for storing hydrofabric data
  #' @param custom_name character class. A custom name to insert into hydrofabric file. Default \code{glue("{lyrs}_")}
  #' @param fileext character class. file extension of hydrofabric file. Default 'gpkg'
  #' @param lyrs character class. The layer name(s) of interest from hydrofabric. Default 'network'.
  #' @param hf_cat_sel boolean. TRUE for a total catchment characterization specific to a single comid, FALSE (or anything else) for all subcatchments
  #' @param overwrite boolean. Overwrite local data when pulling from hydrofabric s3 bucket? Default to FALSE.
  #' @param hf_version character class. The hydrofabric version. When NULL, defaults to same as \code{hfsubsetR::get_subset()}
  #' @param type hydrofabric type. When NULL, defaults to same as \code{hfsubsetR::get_subset()}, likely 'nextgen'
  #' @param domain hydrofabric domain. When NULL, defaults to same as \code{hfsubsetR::get_subset()}, likely 'conus'
  #' @seealso \link[proc.attr.hydfab]{hfab_config_opt} Searches for default arguments from this function using formals
  #' @export

  warning("proc_attr_hf DOES NOT WORK AS EXPECTED!!")

  # Build the hydfab filepath
  name_file <- proc.attr.hydfab:::proc_attr_std_hfsub_name(comid=comid,
                                                           custom_name=glue::glue('{lyrs}_'),
                                                           fileext=fileext)
  fp_cat <- base::file.path(dir_db_hydfab, name_file)

  # Set to the defaults in hfsubsetR if not defined.
  if(is.null(type)){
    type <- base::formals(hfsubsetR::get_subset)$type
  }
  if(is.null(hf_version)){
    hf_version <- base::formals(hfsubsetR::get_subset)$hf_version
  }
  if(is.null(domain)){
    domain <- base::formals(hfsubsetR::get_subset)$domain
  }
  if(is.null(overwrite)){
    overwrite <- base::formals(hfsubsetR::get_subset)$overwrite
  }


  if(!base::dir.exists(dir_db_hydfab)){
    warning(glue::glue("creating the following directory: {dir_db_hydfab}"))
    base::dir.create(dir_db_hydfab)
  }

  # Generate the nldi feature listing ?dataRetrieval::get_nldi_sources()
  nldi_feat <- base::list(featureSource ="COMID",
                          featureID = as.character(comid))

  # Download hydrofabric file if it doesn't exist already
  # Utilize hydrofabric subsetter for the catchment and download to local path
  pkgcond::suppress_warnings(hfsubsetR::get_subset(
    comid = as.character(comid),
    outfile = fp_cat,
    lyrs = lyrs,
    hf_version = hf_version,
    type = type,
    domain = domain,
    overwrite=overwrite),pattern="exists and overwrite is FALSE")

  # Read the hydrofabric file gpkg for each layer
  hfab_ls <- proc.attr.hydfab(path_gpkg=fp_cat,layers=NULL)

  net <- hfab_ls[[lyrs]] %>%
    dplyr::select(divide_id, hf_id) %>%
    dplyr::filter(complete.cases(.)) %>%
    dplyr::group_by(divide_id) %>% dplyr::slice(1)

  if (hf_cat_sel==TRUE){
    # interested in the single location's aggregated catchment data
    net <- net %>% base::subset(hf_id==base::as.numeric(comid))
  }
  return(net)
}

proc_attr_std_hfsub_name <- function(comid,custom_name='', fileext='gpkg'){
  #' @title DEPRECATED. Standardidze hydrofabric subsetter's local filename
  #' @description Internal function that ensures consistent filename
  #' @param comid the USGS common identifier, generated by nhdplusTools
  #' @param custom_name Desired custom name following 'hydrofab_'
  #' @param fileext file extension of the hydrofrabric data. Default 'gpkg'

  hfsub_fn <- base::gsub(pattern = paste0(custom_name,"__"),
                         replacement = "_",
                         base::paste0('hydrofab_',custom_name,'_',comid,'.',fileext))
  return(hfsub_fn)
}


hfab_config_opt <- function(hfab_config,
                            reqd_hfab=c("s3_base","s3_bucket","hf_cat_sel","source")){
  #' @title Configure hydrofabric-relevant optional params
  #' @description If an argument provided in the config file is NULL, first look
  #' for default param value from the \code{proc.attr_hydfab::proc_attr_hf}.
  #' If that is NULL, then look for default value from the
  #' \code{hfsubsetR::get_subset()} args if that param exists there. Otherwise,
  #' uses default param value in \code{proc.attr_hydfab::proc_attr_wrap}.
  #' @param hfab_config The hydrofabric-specific section from the config file, hydfab_config. list.
  #' @param reqd_hfab The non-optional item names in the hydrofabric config file
  #' @return List with default arguments populated corresponding to hfsubetR::get_subset()
  #' @seealso \link[hfsubsetR]{get_subset} Default args referenced using formals here
  #' @export

  # The values inside the hydrofabric configuration section from attr config file
  vals_hfab_config <- lapply(hfab_config, function(x) x[[names(x)]])
  names(vals_hfab_config) <-  base::lapply(hfab_config,
                                           function(x) base::names(x)) %>%
    base::unlist()
  # The required variables in the hydfab_config section:

  sub_hfab_config <- base::within(vals_hfab_config,base::rm(list=reqd_hfab))
  names_sub_hfab <- names(sub_hfab_config)


  xtra_cfig_hfab <- list()
  for(n in names_sub_hfab){
    x <- sub_hfab_config[[n]]
    if(base::is.null(x)){
      # Is this an argument inside proc_attr_hf?
      bool_in_proc_attr_hf <- n %in%
        base::names(base::formals(proc.attr.hydfab:::proc_attr_hf))
      # Is this an argument inside proc_attr_wrap?
      bool_in_proc_attr_wrap <- n %in%
        base::names(base::formals(proc.attr.hydfab::proc_attr_wrap))
      # Is this an argument inside hsubsetR::get_subset?
      bool_in_get_subset <- n %in%
        base::names(base::formals(hfsubsetR::get_subset))

      # Goal: default to value inside proc_attr_hf if default not NULL
      if (!base::is.null(base::formals(proc.attr.hydfab::proc_attr_hf)[[n]])){
        xtra_cfig_hfab[[n]] <- base::formals(proc.attr.hydfab::proc_attr_hf)[[n]]
      } else if (bool_in_get_subset) { # Otherwise use the default value in hfsubsetR::get_subset()
        def_val <- base::formals(hfsubsetR::get_subset)[[n]]
        xtra_cfig_hfab[[n]] <- def_val
      } else if (bool_in_proc_attr_wrap){ # Otherwise Use the wrapper's default value
        xtra_cfig_hfab[[n]] <- base::formals(proc.attr.hydfab::proc_attr_wrap)[[n]]
      }
    } else {
      xtra_cfig_hfab[[n]] <- x
    }
  }
  return(xtra_cfig_hfab)
}
