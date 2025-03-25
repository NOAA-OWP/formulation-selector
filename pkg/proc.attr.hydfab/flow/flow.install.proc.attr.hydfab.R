#' @title Build the formulation-selector R packages
#' @description Following the package building framework as outlined here:
#' https://hilaryparker.com/2014/04/29/writing-an-r-package-from-scratch/
#' Another good resource:
#' https://r-pkgs.org/whole-game.html

# install libraries in case missing
if(!("devtools" %in% rownames(installed.packages()))) install.packages("devtools")
if(!("roxygen2" %in% rownames(installed.packages()))) install.packages("roxygen2")
if(!("testthat" %in% rownames(installed.packages()))) install.packages("testthat")
if(!("covr" %in% rownames(installed.packages()))) install.packages("covr") # To report on unit testing coverage
if(!("htmltools" %in% rownames(installed.packages()))) install.packages("htmltools") # Dependency for coverage report
if(!("DT" %in% rownames(installed.packages()))) install.packages("DT") # Dependency for coverage report
# load libraries
lapply(c("devtools","roxygen2","testthat","covr"), library, character.only = TRUE)[[1]]

# ---------------------------------------------------------------------------- #
#  Define user-specific paths for installation
if ('bolotin' %in% Sys.getenv("HOME")) {
  # if you have a different path to formulation-selector, add it here, otherwise remove
} else if ('choat' %in% Sys.getenv("HOME")){
  # if you have a different path to formulation-selector, add it here, otherwise remove
} else { # assume this is the path to the formulation-selector repo dir
  fs_dir <- file.path(Sys.getenv("HOME"),"git","formulation-selector")
}
# Run unit tests?
RunTest <- FALSE #TRUE Default FALSE prevents s3 data downloading in unit testing (FALSE=fast)
ShowTestCovr <- FALSE # Only possible if RunTest==TRUE. Even slower though.
# ---------------------------------------------------------------------------- #
# Enter in all R packages here
namePack <- c("proc.attr.hydfab")

for(pack in namePack){

  pkg_dir <- file.path(fs_dir,"pkg") # Note that CRAN does not allow '_' in package names, hence the '.'
  if (!dir.exists(pkg_dir)){
    stop(paste0("reconsider the path to ",pkg_dir))
  }

  pack_dir <- file.path(pkg_dir, pack)
  # Test if package name exists, if so don't re-create (just update) it
  # Create package
  if (!file.exists(file.path(pack_dir,"NAMESPACE"))){
    library(usethis)
    # This only happens once when an initial R package is created & is here for future reference
    # Create the initial package framework (should only be run once)
    usethis::create_package(pack_dir)
    setwd(pkg_dir) # testthat setup needs working dir to be the package
    usethis::use_testthat() # setup testthat unit testing
  }


  setwd(pack_dir)

  # Create Roxygen documentation:
  devtools::document()

  # remove any existing version of package in the library location
  try(remove.packages(pack))
  #unloadNamespace("proc.attr.hydfab")

  # Install the package
  setwd(pkg_dir)
  devtools::install(pack)
  detach(paste0("package:", pack), unload=TRUE, character.only = TRUE)
  library(paste0(pack), character.only = TRUE)

  # Run unit tests
  if(RunTest==TRUE){
    setwd(pack_dir)
    devtools::test(pkg="./")
    if(ShowTestCovr==TRUE){
      message('Computing/displaying test coverage...')
      cov <- covr::package_coverage()
      covr::report(cov)
    }
  }
}
