import sys

if sys.version_info < (3, 10):
    NoneType = type(None)
else:
    from types import NoneType  # noqa: F401
