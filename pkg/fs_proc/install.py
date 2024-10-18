'''
title: install the proc_eval_metrics package (and maybe other subpackages as well)
author: Ben Choat <benjamin.choat@noaa.gov>
description: Automates install with execution of single script across OS's
usage: python install.py

Changelog/contributions
    2024-07-02 Originally created, GL
'''

import subprocess # for running command line code from this script
import glob # for bash like file searches including wildcard '*'
import sys # for calling python executable associate with current env

def build_and_install():
    # Build the source distribution and the wheel file
    subprocess.check_call([sys.executable, 'setup.py', 'sdist', 'bdist_wheel'])

    # Find the wheel file
    wheel_files = glob.glob('./dist/*.whl')
    if not wheel_files:
        raise FileNotFoundError("No .whl file found in dist/ directory")
    
    wheel_file = wheel_files[0]

    # Install the wheel file
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', wheel_file])

if __name__ == '__main__':
    build_and_install()