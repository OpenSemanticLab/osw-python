import sys
from pathlib import Path

from pydantic.v1.types import FilePath as PydanticFilePath
from pydantic.v1.validators import path_validator  # , path_exists_validator

if sys.version_info < (3, 10):
    NoneType = type(None)
else:
    from types import NoneType  # noqa: F401
if sys.version_info < (3, 11):
    from backports.strenum import StrEnum  # noqa: F401
else:
    from enum import StrEnum  # noqa: F401


class PossibleFilePath(PydanticFilePath):
    # Overwrite the Pydantic FilePath class to allow non-existing paths
    @classmethod
    def __get_validators__(cls):
        yield path_validator
        # yield path_exists_validator  # Remove this line to allow non-existing paths
        yield cls.validate

    @classmethod
    def validate(cls, value: Path) -> Path:
        return value
