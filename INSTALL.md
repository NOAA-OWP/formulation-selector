# Installation instructions

Detailed instructions on how to install, configure, and get the project running.
<<<<<<< HEAD
<<<<<<< HEAD
=======
=======
>>>>>>> cdab25e2 (cleaning up install guidance and related python install files)

# RaFTS Installation

First, clone the [formulation-selector](https://github.com/NOAA-OWP/formulation-selector) git repo.

```
cd [your-desired-local-directory-here]
git clone https://github.com/NOAA-OWP/formulation-selector.git
cd formulation-selector
```

## Python environment configuration
Then configure your python environment. RaFTS has been developed and tested using Python 3.11 and 3.12:

Instructions are provided here for installing RaFTS with UV, pip, and with conda workflows.

The recommended approach is using the newer uv manager.


### Using uv (suggested)
Install UV (https://docs.astral.sh/uv/getting-started/installation/)

Windows:
- powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
Linux and macOS:
- Use curl to download the script and execute it with sh:
- curl -LsSf https://astral.sh/uv/install.sh | sh

- If your system doesn't have curl, you can use wget:
- wget -qO- https://astral.sh/uv/install.sh | sh

2. Create a virtual environment:
- Navigate to the install directory of RaFTS in the command line (e.g., C:/GITDIR/formulation-selector/install),
   - e.g., ```cd C:/GITDIR/formulation-selector/install```

- With UV, you can specify the python version when creating your virtual environment
   - E.g., If I use ```--python 3.11``` as a flage to create my virtual environment, that environment will have python 3.11 associated with it.

   - ```uv venv ../.venv --python 3.11```

   - NOTE: .venv will be the name of your virtual environment and it will be at formulation-selector/.venv
- Activate your new virtual environment:
- Windows:
   - ```../.venv/Script/activate```
- Linux or macOS:
   - ```source ../.venv/bin/activate```

3. Install the python dependencies:
   - ```uv install -r requirements.txt```


### Using pip
1. If you choose to use pip, you must install python independently.
- https://www.python.org/downloads/

2. Create a virtual environment:
- Navigate to the install directory of RaFTS in the command line (e.g., C:/GITDIR/formulation-selector/install),
   - e.g., ```cd C:\GITDIR\formulation-selector/install```
- The python.exe you use to create the virtual environment defines which python version will be associated with you environment.
   - E.g., If I use python3.11/python.exe to create my virtual environment, that environment will have python 3.11 associated with it.
   - If you want to specify a specific python version other than the default in your path, you can point to it explicitly, e.g.,
   - ```../Path/To/Your/Python/python.exe -m venv ../.venv```
   - Or use the default python version,
   - ```python -m venv ../.venv```
   - NOTE: .venv will be the name of your virtual environment and it will be at formulation-selector/.venv
- Activate your new virtual environment:
- Windows:
   - ```../.venv/Script/activate```
- Linux or macOS:
   - ```source ../.venv/bin/activate```

3. Install the python dependencies:
   - ```python -m pip install -r ./install/requirements.txt```


### Using Conda
1. If you want to use Conda, you must install Conda independently.
- [https://www.anaconda.com/docs/getting-started/miniconda/install]
- Here are some options for installing miniconda from command line:
   - Windows (Command Prompt):
      - ```curl https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -o .\miniconda.exe```
      - ```start /wait "" .\miniconda.exe /S```
      - ```del .\miniconda.exe```
   - Windows (PowerShell)
      - ```wget "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe" -outfile ".\miniconda.exe"```
      - ```Start-Process -FilePath ".\miniconda.exe" -ArgumentList "/S" -Wait```
      - ```del .\miniconda.exe```
      - To work in Powershell or Command Prompt using conda, you will need to do ONE of the following
         - open *Anaconda Powershell Prompt* (recommended)
         - open *Anaconda Prompt*
         - add conda to your Path
            - this link has good instructions [https://stackoverflow.com/questions/44515769/conda-is-not-recognized-as-internal-or-external-command]
   - macOS
      - ```mkdir -p ~/miniconda3```
      - ```curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o ~/miniconda3/miniconda.sh```
      -  ```bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3```
      - ```rm ~/miniconda3/miniconda.sh```
      - Close and reopen your terminal to activate the newly install conda instance.
   - Linux (64-bit)
      - ```mkdir -p ~/miniconda3```
      - ```wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh```
      - ```bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3```
      - ```rm ~/miniconda3/miniconda.sh```
      - Close and reopen your terminal to activate the newly install conda instance.

2. Create a virtual environment:
- Navigate to the install directory of RaFTS (e.g., C:/GITDIR/formulation-selector/install),
   - e.g., ```cd C:\GITDIR\formulation-selector/install```
- By default the environment will be named *rafts_env*. If you would like to change the name, open *install/requirements.yml* and update the *name: rafts_env* option with your preferred environment name.

3. Install the python dependencies:
   - Create the conda environment installing python 3.12 and all dependencies.
   - ```conda env create --file=install/requirements.yml```



## R environment configuration
Then configure your R environment. RaFTS has been developed and tested using R 4.4.0 and 4.4.2.

<<<<<<< HEAD
TODO: Fill out better R install instructions
=======
For RaFTS, we set a project-specific library
>>>>>>> cdab25e2 (cleaning up install guidance and related python install files)


## Install the `proc.attr.hydfab` R Package
The features of the formulation-selector that acquire catchment attributes that feed into the model prediction algorithm (which, as noted above, is in Python) are written in R to promote compatibility with the [NOAA-OWP/hydrofabric](https://github.com/NOAA-OWP/hydrofabric).

Modify the path to `fs_dir` inside
[flow.install.proc.attr.hydfab.R](https://github.com/NOAA-OWP/formulation-selector/tree/main/pkg/proc.attr.hydfab/flow/flow.install.proc.attr.hydfab.R)

If you do not wish to run unit tests, set `RunTest <- FALSE` inside this install script.

Then run the `flow.install.proc.attr.hydfab.R` script inside RStudio.

**IMPORTANT** The arrow package may not play nicely with parquet file read/write. If you experience an error like that in Issue #34, try installing the arrow package with the following command:
```
install.packages("arrow", repos = c("https://apache.r-universe.dev"))
```
Note that this may generally reduce the number of headaches if you go ahead and install arrow from apache.r-universe.dev in lieu of CRAN.

<<<<<<< HEAD
>>>>>>> 19454933 (cleaning R-related commentary - not much there and needs to be cleaned up/filled out with details)
=======
>>>>>>> cdab25e2 (cleaning up install guidance and related python install files)
