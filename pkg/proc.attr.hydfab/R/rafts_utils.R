# A collection of convenience functions used in some RaFTS scripts that are not
#. core to RaFTS processing (e.g. not dependent on generating data for further
#. use in the python rafts_algo package)

# Changelog / Contributions
# 2025-08-14 Added logr, GL
library(arrow)
library(dplyr)
library(nhdplusTools)
library(glue)
library(sf)
library(data.table)
library(logr)

retrieve_attr_exst <- function(comids, vars, dir_db_attrs, bucket_conn=NA){
  #' @title Grab previously-aggregated attributes from locations of interest
  #' @description Retrieves existing attribute data already stored in the
  #' dir_db_attrs directory as .parquet files & return tbl of all comids and
  #' attributes of interest.
  #' @details Only considers data already generated inside dir_db_attrs. If
  #' more data are needed, acquire attribute data acquisition using proc_attr_wrap().
  #' Runs checks on input arguments and retrieved contents, generating warnings
  #' if requested comids and/or variables were completely absent from the dataset
  #' @param comids character class. The comids/hf_uids/etc. of interest.
  #' @param vars character class. The attribute variables of interest.
  #' @param dir_db_attrs character class. The path where data
  #' @param bucket_conn Default NA. Placeholder in case a bucket connection is
  #' ever created
  #' @seealso \link[proc.attr.hydfab]{proc_attr_wrap}
  #' @export
  # Changelog/Contributions
  #  2024-07-26 Originally created, GL

  # Run checks on input args
  if(!'character' %in% base::class(comids) ){
    # Let's try unlisting and unnaming just-in-case
    comids <- comids %>% base::unlist() %>% base::unname()
    if(!'character' %in% base::class(comids) ){
      warn_msg <- "comids expected to be character class. converting"
      logr::log_print(warn_msg,level="WARN")
      comids <- base::as.character(comids)
    }
  }
  if(!'character' %in% base::class(vars)){
    # Let's try unlisting and unnaming just-in-case
    vars <- vars %>% base::unlist() %>% base::unname()
    if(!'character' %in% base::class(vars)){
      stop_msg <- "vars expected to be character class"
      logr::log_print(stop_msg,level="ERROR")
      stop()
    }
  }
  if(!base::dir.exists(dir_db_attrs)){
    stop_msg <- glue::glue("The attribute database path does not exist:
                      {dir_db_attrs}")
    logr::log_print(stop_msg,level="ERROR")
    stop()
  }
  if(!any(base::grepl(".parquet", base::list.files(dir_db_attrs)))){
    warn_msg <- glue::glue("The following path does not contain expected
                          .parquet files: {dir_db_attrs}")
    logr::log_print(warn_msg,level="WARN")
  }

  if(base::is.na(bucket_conn)){
    # Query based on COMID & variables, then retrieve data
    parq_files <- file.path(dir_db_attrs,list.files(dir_db_attrs, pattern = "parquet"))
    dat_all_attrs <- try(arrow::open_dataset(parq_files, format = 'parquet') %>%
                           dplyr::mutate(across(where(is.factor), as.character)) %>% # factors are a pain!!
                           dplyr::filter(featureID %in% !!comids) %>%
                           dplyr::filter(attribute %in% !!vars) %>%
                           dplyr::distinct() %>%
                           dplyr::collect(),silent=TRUE)

    if('try-error' %in% base::class(dat_all_attrs)){
      stop_msg <- glue::glue("Could not acquire attribute data from {dir_db_attrs}")
      logr::log_print(stop_msg,level="ERROR")
      stop()
    }
  } else {# TODO add bucket connection here if it ever becomes a thing
    stop_msg <- "Need to accommodate a different type of source here, e.g. s3"
    logr::log_print(stop_msg,level="ERROR")
    stop()
  }

  # Run simple checks on retrieved data
  if (base::any(!comids %in% dat_all_attrs$featureID)){
    missing_comids <- comids[base::which(!comids %in% dat_all_attrs$featureID)]
    if (length(missing_comids) > 0){
      warn_msg <- base::paste0("Datasets missing the following comids: ",
                           base::paste(missing_comids,collapse=","),
                           "\nConsider running proc.attr.hydfab::proc_attr_wrap()")
      logr::log_print(warn_msg,level="WARN")
    } else {
      logr::log_print("There's a logic issue on missing_comids inside retrieve_attr_exst",level="INFO")
    }


  }

  if (base::any(!vars %in% dat_all_attrs$attribute)){
    missing_vars <- vars[base::which(!vars %in% dat_all_attrs$attribute)]
    if(length(missing_vars) >0 ){
      warn_msg <- base::paste0("Datasets entirely missing the following vars: ",
                           base::paste(missing_vars,collapse=","),
                           "\nConsider running proc.attr.hydfab::proc_attr_wrap()")
      logr::log_print(warn_msg,level="WARN")
    } else {
      logr::log_print("There's a logic issue on missing_vars inside retrieve_attr_exst",
                      level="WARN")
    }

  }

  # Run check on all comid-attribute pairings by counting comid-var pairings
  sum_var_df <- dat_all_attrs %>%
    dplyr::group_by(featureID) %>%
    dplyr::summarise(dplyr::n_distinct(attribute))
  idxs_miss_vars <- base::which(sum_var_df$`n_distinct(attribute)` != length(vars))
  if(base::length(idxs_miss_vars)>0){
    warn_msg <- glue::glue("The following comids are missing desired variables:
              {paste(sum_var_df$featureID[idxs_miss_vars],collapse='\n')}
                       \nConsider running proc.attr.hydfab::proc_attr_wrap()")
    logr::log_print(warn_msg,level="WARN")
  }

  return(dat_all_attrs)
}

std_dir_logs <- function(dir_db_attrs){
  #' @title Define the standard directory used for storing log files
  #' @param dir_db_attrs The path where attribute data are stored
  #' @seealso rafts_prep.std_dir_log (python w/ different arg)
  #' @export
  base_dir <- dir_db_attrs %>% base::dirname() %>% base::dirname()
  dir_log <- file.path(base_dir,"logs")
  if(!base::dir.exists(dir_log)){
    base::dir.create(dir_log,recursive=TRUE)
  }
  return(dir_log)
}

std_path_log <- function(dir_log, path_attr_config,script=''){
  #' @title Define the path for storing log file specific to an atttribute config
  #' @param dir_log The RaFTS project's standard log directory
  #' @param path_attr_config Filepath to the attribute config file
  #' @param script The string of the script name to add to the log's filename. Default ''.
  #' @seealso rafts_prep.std_path_log (python similar w/ different args)
  #' @export
  ds_dir <- base::basename(base::dirname(path_attr_config))
  config_fn <- base::basename(tools::file_path_sans_ext(path_attr_config))
  if(script!=''){
    script = base::paste0("_",script)
  }
  log_path <- file.path(dir_log,ds_dir, paste0(config_fn,script,".log"))
  if(!base::dir.exists(base::dirname(log_path))){
    base::dir.create(base::dirname(log_path),recursive=TRUE)
  }
  return(log_path)
}

std_dir_gpkg_chunk_nhdp_geom <- function(dir_save_nhdp){
  #' @title Generate the chunk subdirectory for temporarily storing results
  #' @description Recursively creates the chunk directory if it doesn't exist
  #' @param dir_save_nhdp The base directory location containing the chunk dir
  #' @seealso \link[proc.attr.hydfab]{dl_nhdplus_geoms_wrap}
  # Place the geopackage chunks here
  dir_save_nhdp_chunk <- file.path(dir_save_nhdp,"chunk")

  if(!base::dir.exists(dir_save_nhdp_chunk)){
    base::dir.create(dir_save_nhdp_chunk,recursive = TRUE)
  }

  return(dir_save_nhdp_chunk)
}

std_path_gpkg_chunk_nhdp_geom <- function(dir_save_nhdp,seq_num){
  #' @title standardize each chunked filepath
  #' @param dir_save_nhdp The base directory location containing the chunk dir
  #' @param seq_num The unique number defining the chunk sequence (expected to
  #' integer from 1 to n number of chunked files)
  #' @seealso \link[proc.attr.hydfab]{dl_nhdplus_geoms_wrap}
  dir_save_nhdp_chunk <- proc.attr.hydfab:::std_dir_gpkg_chunk_nhdp_geom(dir_save_nhdp)
  path_gpkg_chunk <- glue::glue(base::file.path(dir_save_nhdp_chunk,
                             "nhdp_chunked_{seq_num}.gpkg"))
  return(path_gpkg_chunk)
}

std_path_rds_chunk_nhdp_geom <- function(path_gpkg_chunk){
  #' @title the standardized filepath for chunked RDS files
  #' @param path_gpkg_chunk The full filepath to a chunked .gpkg
  #' @seealso \link[proc.attr.hydfab]{dl_nhdplus_geoms_wrap}
  #' @seealso \link[proc.attr.hydfab]{std_path_gpkg_chunk_nhdp_geom}
  path_rds <- base::gsub(pattern="gpkg",replacement="rds",path_gpkg_chunk)
  return(path_rds)
}



std_path_gpkg_all_nhdp_geom <- function(dir_save_nhdp,filename_str){
  #' @title the standardized path for saving all geopackages
  #' @param dir_save_nhdp The directory location to store data
  #' @param filename_str The filename string to use for compiled output data
  #' @seealso \link[proc.attr.hydfab]{dl_nhdplus_geoms_wrap}
  if(!is.null(filename_str)){
    custom_filename <- glue::glue("nhdp_cat_line_out_{filename_str}.gpkg")
  } else {
    custom_filename <- glue::glue("nhdp_cat_line_out.gpkg")
  }

  # Write complete geopackage:
  path_save_gpkg_all <- file.path(dir_save_nhdp,custom_filename)
  return(path_save_gpkg_all)
}

std_write_gpkg_all_nhdp_geom <- function(df_obj,path_save_gpkg_all,layer_save =
                                 c('catchment','flowlines','outlet','input_df')[4]){
  #' @title Write standardized .gpkg file, enforcing expected layer names
  #' @param df_obj The dataframe/sf nhdplus geometry or input data
  #' @param path_save_gpkg_all The gpkg filepath for writing
  #' @param layer_save The standardized names for saving different types of
  #' layers to the geopackage file.
  #' @seealso \link[proc.attr.hydfab]{dl_nhdplus_geoms_wrap}
  if(!base::grepl(".gpkg",path_save_gpkg_all)){
    stop_msg <- "Expect `path_save_gpkg_all` to be a .gpkg filepath"
    logr::log_print(stop_msg,level="ERROR")
    stop()
  }
  if(base::length(layer_save) !=1){
    stop_msg <- "Expecting only one layer name. Refer to `layer_save` in
         std_write_gpkg_all_nhdp_geom"
    logr::log_print(stop_msg,level="ERROR")
    stop()
  }
  accepted_layers <- c('catchment','flowlines','outlet','input_df')
  if(!any(layer_save %in% accepted_layers)){
    newline_layer_names <- paste0(accepted_layers,collapse="\n")
    stop_msg <- glue::glue("Must provide layer_save as one of the following names:
                    {newline_layer_names}")
    logr::log_print(stop_msg,level="ERROR")
    stop()
  }

  rslt <- try(sf::st_write(df_obj,path_save_gpkg_all,layer=layer_save,
                           append=FALSE,quiet=TRUE))

  if('try-error' %in% base::class(rslt)){
    warn_msg <- glue::glue("COULD NOT WRITE {layer_save} to {path_save_gpkg_all}!")
    logr::log_print(warn_msg,level="WARN")
  }
}


compile_chunks_ndplus_geoms <- function(dir_save_nhdp,seq_nums=NULL,
                                        filename_str=NULL){
  #' @title Compile chunked NHDPlus-retrieved geospatial datasets
  #' @param dir_save_nhdp The base directory location to store data
  #' @param seq_nums The numbers expected in each chunked filename
  #' @param filename_str The custom string for writing data to file
  #' @return A compiled list of the geospatial data, containing:
  #' \itemize{
  #' \item `catchment` The catchment boundaries NHDplus dataset
  #' \item `flowlines` The flowlines NHDplus dataset
  #' \item `outlet` The catchment outlet NHDplus dataset
  #' \item `input_dt` The input data.table with data used to query NHDplus
  #' \item `path_gpkg_compiled` File path of the saved geopackage
  #' }
  #' @seealso \link[proc.attr.hydfab]{dl_nhdplus_geoms_wrap}
  # Changelog/contributions
  #. 2025-03-20 Originall created, GL
  # Compile entire dataset

  dir_save_nhdp_chunk <- proc.attr.hydfab:::std_dir_gpkg_chunk_nhdp_geom(dir_save_nhdp)

  all_files_rds <- base::list.files(dir_save_nhdp_chunk,pattern = "rds")

  # Subset to seq_nums of interest:
  all_files_rds_ls <- base::lapply(seq_nums,function(x)
    base::list.files(dir_save_nhdp_chunk,pattern = paste0("_",as.character(x),".rds")))
  all_files_rds <- all_files_rds_ls %>% base::unlist()

  if(base::length(all_files_rds) == 0){
    warn_msg <- "No rds files match expected sequence number formats in filenames. Reading all rds files."
    logr::log_print(warn_msg,level="WARN")
    all_files_rds <- list.files(dir_save_nhdp_chunk, pattern = '.rds')
  } else if(base::length(all_files_rds)<length(seq_nums)){
    logr::log_print("Not all expected chunked files present.",level="WARN")
  }

  ls_nhdp_all <- base::lapply(all_files_rds, function(x)
    base::readRDS(base::file.path(dir_save_nhdp_chunk,x)))
  sf_cats_all <- base::lapply(ls_nhdp_all, function(x) x$catchment) %>%
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE) # %>%
  #sf::st_as_sf(crs=4326)
  sf_flowlines_all <- base::lapply(ls_nhdp_all, function(x) x$flowline) %>%
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE) #%>%
  #sf::st_as_sf(crs=4326)
  sf_outlets_all <- lapply(ls_nhdp_all, function(x) x$outlet) %>%
    data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE)#%>%
  #sf::st_as_sf(crs=4326)


  # Munging: catchment may contain multipolygons. These should be singular:
  tot_polys <- base::lapply(sf_cats_all$geometry, function(x) length(x)) %>% unlist()
  idxs_polys <- base::which(tot_polys>1) # The multipolygon rows
  ls_poly <- base::lapply(idxs_polys, function(i) sf_cats_all$geometry[i] %>% sf::st_union() %>%
                            sf::st_cast("POLYGON") %>% unique())
  sf_cats_union <- sf_cats_all
  ctr <- 0
  for(idx_poly in idxs_polys){
    ctr <- ctr+1
    sf_cats_union$geometry[idx_poly] <- ls_poly[[ctr]]
  }


  path_save_gpkg_all <- proc.attr.hydfab:::std_path_gpkg_all_nhdp_geom(dir_save_nhdp,
                                                             filename_str)
  # Write complete geopackage:
  proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=sf_cats_union,
                                                  path_save_gpkg_all,
                                                  layer_save = 'catchment')
  proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=sf_flowlines_all,
                                                  path_save_gpkg_all,
                                                  layer_save = 'flowlines')
  proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=sf_outlets_all,
                                                  path_save_gpkg_all,
                                                  layer_save = 'outlet')

  # Write the input dataframe
  all_list_names <- lapply(ls_nhdp_all, function(ls) names(ls)) %>%
    base::unlist() %>% unique()
  if('input_df' %in% all_list_names){
    ls_input_df <- lapply(ls_nhdp_all, function(ls) ls[['input_df']])
    input_dt <- data.table::rbindlist(ls_input_df,fill=TRUE, use.names=TRUE,
                                         ignore.attr=TRUE)
    try(sf::st_write(input_dt,path_save_gpkg_all,layer='input_df',append=FALSE,quiet=TRUE))
  } else {
    input_dt <- data.table()
  }
  print("Completed chunked nhdplus dataset compiling")

  ls_compiled_data <- list(catchment = sf_cats_union,
                           flowlines = sf_flowlines_all,
                           outlet = sf_outlets_all,
                           input_dt=input_dt,
                           path_gpkg_compiled = path_save_gpkg_all)
  return(ls_compiled_data)
}




dl_nhdplus_geoms_wrap <- function(df,col_id, dir_save_nhdp,filename_str,
                                  id_type = c("comid","AOI")[1],
                                  keep_cols=c(NULL,"all")[1],
                                  seq_size = 390,
                                  overwrite_chunk=FALSE){
  #' @title Grab all nhdplus geometries/comids: outlet, flowlines, catchment
  #' @author Guy Litt
  #' @description Retrieve all nhdplus layers for a comid/AOI, and download/save data
  #' in chunks at hourly intervals to account for external database hits
  #' @details If AOI selected, the area of interest is assumed to be a line, and
  #' the midpoint is selected for querying NLDI.
  #' Recommended to stick to a certain seq_size (e.g. default) to easily re-use
  #' file chunks when `overwrite_chunk` is FALSE.
  #' @param df dataframe with location information that `get_nhdplus` uses
  #' @param col_id The column in the dataframe corresponding to the id
  #' @param dir_save_nhdp The directory location to store data
  #' @param filename_str The filename string to use for compiled output data
  #' @param seq_size the size of the sequence of ids to query within an hour. Recommend <400
  #' @param id_type the type of id corresponding to `col_id`. Default 'comid'. 'AOI' may be used for geospatial queries
  #' @param keep_cols the columns inside `df` to also save. May be 'all'. Default NULL means no df data written to file
  #' @param overwrite_chunk Should file chunks be overwritten? Default FALSE means skipping database connection & file chunking if a data sequence already created
  #' @seealso gen_pred_locs_rfcs.R script
  #' @export
  # Changelog/Contributions
  #  2025-03-20 Originally created, GL

  if(keep_cols == 'all'){
    keep_cols <- base::colnames(df)
  }
  # Generate the chunk subdirectory for temporarily storing results
  dir_save_nhdp_chunk <- proc.attr.hydfab:::std_dir_gpkg_chunk_nhdp_geom(dir_save_nhdp)

  path_save_gpkg_all <- proc.attr.hydfab:::std_path_gpkg_all_nhdp_geom(dir_save_nhdp,
                                                                       filename_str)

  if(!base::is.null(keep_cols) && overwrite_chunk == FALSE &&
     base::file.exists(path_save_gpkg_all)){
    # Check if the input data have been saved to file
    all_layrs <- sf::st_layers(path_save_gpkg_all) # Check if all layers accounted for
    if(!'input_df' %in% all_layrs$name){ # Overwrite
      # Find the keep column:
      df_keep <- df[,keep_cols]

      # Write the keep column to file
      proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=df_keep,
                              path_save_gpkg_all,
                              layer_save = 'input_df')
    }
  }
  # Perform chunking
  seq_nums <- base::c(base::seq(from=1,base::nrow(df),seq_size),base::nrow(df))[-1]
  ls_nhdp_all <- list()
  ctr_seq <- 0
  for(seq_num in seq_nums){
    path_gpkg_chunk <- proc.attr.hydfab:::std_path_gpkg_chunk_nhdp_geom(dir_save_nhdp,seq_num)
    if(base::file.exists(path_gpkg_chunk) && overwrite_chunk==FALSE){
      next()
    }

    ctr_seq <- ctr_seq + 1
    print(glue::glue("Performing sequence up to {seq_num} of {base::nrow(df)}"))
    if(ctr_seq == 1){
      sub_df <- df[1:seq_num,]
    } else {
      begn_seq <- seq_nums[ctr_seq-1] + 1
      sub_df <- df[begn_seq:seq_num,]
    }

    ids_sub <- sub_df[[col_id]]
    # Now acquire the attributes:
    ls_nhdp_chunk <- list()
    for(ctr in 1:length(ids_sub)){
      if(id_type == "comid"){
        # Retrieve the data for a comid
        id <- ids_sub[ctr]
        nhdp_all <- try(nhdplusTools::get_nhdplus(comid = id, realization = 'all'))
      } else if (id_type == "AOI"){
        # # Reinforce geometry column naming
        # sf::st_geometry(sub_df) <- col_id
        geom_row <- sub_df[ctr,col_id]
        if(is.null(sf::st_crs(geom_row))){
          warn_msg <- "UNKNOWN CRS FOR PROVIDED AOI IN df!!
                  Strongly recommend ensuring appropriate CRS before passing into dl_nhdplus_geoms_wrap()"
          logr::log_print(warn_msg,level="WARN")
        }
        aoi_pt <- geom_row[[col_id]] %>% sf::st_cast("LINESTRING") %>%
          #sf::st_segmentize(dfMaxLength = 100) %>%
          sf::st_line_sample(sample = 0.5) %>%
          sf::st_cast("POINT")
        id <- aoi_pt
        nhdp_all <- try(nhdplusTools::get_nhdplus(AOI = aoi_pt, realization = 'all'))
      }


      if("try-error" %in% class(nhdp_all)){
        warn_msg <- glue::glue("Could not retrieve comid for {id}")
        logr::log_print(warn_msg,level="WARN")
      } else {
        ls_nhdp_chunk[[ctr]] <- nhdp_all
      }
    }
    ###### COMPILE CHUNKS AND WRITE TO FILE #######
    # combine the catchment data:
    sf_cats <- lapply(ls_nhdp_chunk, function(x) x$catchment) %>%
      data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE) %>%
      sf::st_as_sf(crs=4326)

    sf_flowlines <- lapply(ls_nhdp_chunk, function(x) x$flowline) %>%
      data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE)%>%
      sf::st_as_sf(crs=4326)
    sf_outlets <- lapply(ls_nhdp_chunk, function(x) x$outlet) %>%
      data.table::rbindlist(fill=TRUE,use.names=TRUE,ignore.attr=TRUE)%>%
      sf::st_as_sf(crs=4326)


    # Write chunked geopackage files:
    proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=sf_cats,
                                          path_save_gpkg_all = path_gpkg_chunk,
                                          layer_save = 'catchment')

    proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=sf_flowlines,
                                          path_save_gpkg_all = path_gpkg_chunk,
                                          layer_save = 'flowlines')

    proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=sf_outlets,
                                        path_save_gpkg_all = path_gpkg_chunk,
                                        layer_save = 'outlet')
    if(!base::is.null(keep_cols)){ # Save to file data from the original dataframe
      df_keep <- df[,keep_cols]
      proc.attr.hydfab:::std_write_gpkg_all_nhdp_geom(df_obj=df_keep,
                                          path_save_gpkg_all = path_gpkg_chunk,
                                          layer_save = 'input_df')
    }
    path_rds <- proc.attr.hydfab:::std_path_rds_chunk_nhdp_geom(path_gpkg_chunk)
    ls_nhdp_chunk <- base::list(catchment = sf_cats,
                          flowline=sf_flowlines,outlet = sf_outlets)
    if(!base::is.null(keep_cols)){
      ls_nhdp_chunk[['input_df']] <- df[,keep_cols]
    }
    # Write list of chunks to file
    base::saveRDS(ls_nhdp_chunk,path_rds)

    if(seq_num < base::max(seq_nums)){
      print("Pausing NLDI queries for 61 minutes")
      Sys.sleep(60*61) # 400 NLDI queries per hour
    }
  } # End loop over chunks

  # Compile the chunks into a list of sf objects / data.table
  ls_compiled_data <- proc.attr.hydfab:::compile_chunks_ndplus_geoms(
                    dir_save_nhdp=dir_save_nhdp,seq_nums=seq_nums,
                    filename_str=filename_str)

  return(ls_compiled_data)
}
