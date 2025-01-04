from setuptools import setup, find_packages
# Instructions on package data files: https://sinoroc.gitlab.io/kb/python/package_data.html
# Instructions for build & install in terminal:
# > cd /path/to/fs_algo/
# > python setup.py sdist bdist_wheel
# > pip install -e ./
setup(
    include_package_data=True,
    package_data={'' : ['./data/*.yaml']},
    name="fs_algo",
    version="0.0.2.2",
    author="Guy Litt, Ben Choat, Lauren Bolotin",
    author_email="guy.litt@noaa.gov",
    description="A package for predicting hydrologic formulation metrics and signatures based on catchment attributes.",
    packages=find_packages(),
    install_requires=[ 
        'pandas',
        'pyyaml',
        'wheel',
        'xarray',
        'zarr',
        'scikit-learn',
        'pynhd',
        'dask',
        'dask_expr'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)