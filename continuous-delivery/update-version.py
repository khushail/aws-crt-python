#!/usr/bin/env python3

import os
import re
import subprocess

tag = subprocess.check_output(['git', 'describe', '--tags'])
# strip the leading v
version = str(tag[1:].strip(), 'utf8')
# convert 0.2.12-2-g50254a9 to 0.2.12
current_version = version.split("-")[0]
init_path = os.path.join(os.path.dirname(__file__), '..', 'awscrt', '__init__.py')
print("Updating awscrt.__version__ to version {}".format(current_version))
contents = None
with open(init_path, 'r+') as init_py:
    contents = init_py.read()

contents = re.sub(r"__version__ = '1\.0\.0-dev'", r"__version__ = '{}'".format(current_version), contents)

with open(init_path, 'w') as init_py:
    init_py.write(contents)

# setup = contents[contents.rfind('setuptools.setup'):]
# print(setup)
