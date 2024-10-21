# This file is required to make Python treat directories containing the file as
#  packages.
# Additionally, classes from multiple files are imported to allow easy access via
#  'osw.controller.<ClassName>

import inspect

import osw.model.entity as model

# imports of controllers for always present models
# note: to keep this import auto-removal per pre-commit hook is disabled
from osw.controller.entity import Entity  # noqa: F401

# conditional imports
# Note: does not work if the module is imported before the model is loaded
models = [m[0] for m in inspect.getmembers(model)]

if "Database" in models:
    from osw.controller.database import DatabaseController  # noqa: F401
