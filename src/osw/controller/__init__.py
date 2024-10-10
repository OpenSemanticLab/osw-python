# This file is required to make Python treat directories containing the file as
#  packages.
# Additionally, classes from multiple files are imported to allow easy access via
#  'osw.controller.<ClassName>

import inspect

import osw.model.entity as model

# imports of controllers for always present models

# conditional imports
models = [m[0] for m in inspect.getmembers(model)]

if "Database" in models:
    pass
