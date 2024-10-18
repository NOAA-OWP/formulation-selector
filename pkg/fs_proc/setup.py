from setuptools import setup, find_packages
# Instructions on package data files: https://sinoroc.gitlab.io/kb/python/package_data.html
# Instructions for build & install in terminal:
# > cd /path/to/fs_proc/
# > python setup.py sdist bdist_wheel
# > pip install -e ./
setup(
    include_package_data=True,
    package_data={'' : ['./data/*.yaml']},
    name="fs_proc",
    version="0.1.4",
    author="Guy Litt, Ben Choat, Lauren Bolotin",
    author_email="guy.litt@noaa.gov",
    description="A simple package for processing data in the formulation selection decision support tool",
    packages=find_packages(),
    install_requires=[ 
        'pandas',
        'pyyaml',
        'wheel',
        'xarray',
        'zarr'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)