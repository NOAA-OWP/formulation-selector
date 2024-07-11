from setuptools import setup, find_packages
# Instructions on package data files: https://sinoroc.gitlab.io/kb/python/package_data.html
# Instructions for build & install in terminal:
# > cd /path/to/fsds_proc/
# > python setup.py sdist bdist_wheel
# > pip install -e ./
setup(
    include_package_data = True,
    #package_data = {'fsds_proc' : ['data/*.yaml']},
    name="fsds_proc",
    version="0.1.3",
    author="Guy Litt",
    author_email="guy.litt@noaa.gov",
    description="A simple package for processing data in the formulation selection decision support tool",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)