from __future__ import annotations

import re
from pathlib import Path
from typing import List, Union

from pydantic.v1 import PrivateAttr, validator

from osw.model.static import OswBaseModel

PACKAGE_ROOT_PATH = Path(__file__).parents[1]
BASE_PATH = Path.cwd()
OSW_FILES_DIR_DEFAULT = BASE_PATH / "osw_files"
DOWNLOAD_DIR_DEFAULT = OSW_FILES_DIR_DEFAULT / "downloads"
CRED_FILENAME_DEFAULT = "accounts.pwd.yaml"
CRED_FILEPATH_DEFAULT = OSW_FILES_DIR_DEFAULT / CRED_FILENAME_DEFAULT
WIKI_DOMAIN_DEFAULT = "wiki.open-semantic-lab.org"


class FilePathDefault(OswBaseModel):
    """A class to store the default file path. This is a helper class to make the
    default file path, defined within this module, accessible from a calling script."""

    _default: Union[Path] = PrivateAttr(BASE_PATH)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, path: Union[str, Path] = BASE_PATH):
        data = {"_default": Path(path) if isinstance(path, str) else path}
        super().__init__(**data)

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return f"FilePathDefault(path={self.path})"

    def __eq__(self, other):
        other_path = getattr(other, "path", None)
        if other_path is None:
            return False

    @property
    def path(self):
        return self._default

    def set(self, new: Union[str, Path]):
        self._default = Path(new) if isinstance(new, str) else new

    def get(self):
        return self._default


class Paths(OswBaseModel):
    """A class to store the default paths. This is a helper class to make the default
    paths, defined within this module, accessible from a calling script."""

    base: Path = BASE_PATH
    """If you want to have the sub folders created in an directory that is not the
    current working directory of the calling script, use Path.base = new_path."""
    osw_files_dir: Path = OSW_FILES_DIR_DEFAULT
    """If you want to specify the default OSW files directory, use
    Path.osw_files_dir = new_path."""
    cred_filepath: Path = CRED_FILEPATH_DEFAULT
    """If you want to specify the saving location of the credentials file, use
    Path.cred_filepath = new_path."""
    download_dir: Path = DOWNLOAD_DIR_DEFAULT
    """If you want to specify the default download directory, use
    Path.download_dir = new_path."""
    _changed: List[str] = PrivateAttr(default_factory=list)
    """A flag to indicate if any of the paths have been changed."""

    def __init__(self, **data):
        super().__init__(**data)
        self._changed = [key for key in data.keys() if key != "_changed"]

    def __setattr__(self, name, value):
        old_value = getattr(self, name)
        super().__setattr__(name, value)
        self.on_attribute_set(name, value, old_value)
        if name not in self._changed:
            self._changed.append(name)

    def has_changed(self, name):
        return name in self._changed

    @property
    def changed(self):
        return self._changed

    def on_attribute_set(self, attr_name, new_value, old_value):
        """
        This method is called every time an attribute is set. It is used to update the
        paths that are dependent on the [base, osw_files_dir] path when the
        [base, osw_files_dir] path is changed.

        Parameters
        ----------
        attr_name:
            The name of the attribute that was set
        new_value
            The new value the attribute was set to
        old_value
            The value the attribute had before it was set
        """

        def update_attr(set_attr, to_update, old_val, new_val):
            for attr_name in to_update:
                if old_val in getattr(self, attr_name).parents:
                    old_rel_path = getattr(self, attr_name).relative_to(old_val)
                    new_rel_path = new_val / old_rel_path
                    setattr(self, attr_name, new_rel_path)
                    print(
                        f"Following the setting of {self.__name__}.{set_attr}, "
                        f"{self.__name__}.{attr_name} was updated to {new_rel_path}."
                    )

        if attr_name == "base":
            update_attr(
                "base",
                ["osw_files_dir", "cred_filepath", "download_dir"],
                old_value,
                new_value,
            )
        elif attr_name == "osw_files_dir":
            update_attr(
                "osw_files_dir", ["cred_filepath", "download_dir"], old_value, new_value
            )


# Create an instance of the Paths class to make the default paths accessible from a
# calling script.
paths = Paths()
"""To overwrite a default path, execute, e.g.,: paths.base = new_path"""


class Params(OswBaseModel):
    """A class to store the default parameters. This is a helper class to make the
    default parameters, defined within this module, accessible from a calling script."""

    wiki_domain: str = WIKI_DOMAIN_DEFAULT
    """The default domain of the OSW instance to interact with."""
    _changed: List[str] = PrivateAttr(default_factory=list)
    """A flag to indicate if any of the parameters have been changed."""

    def __init__(self, **data):
        super().__init__(**data)
        self._changed = [key for key in data.keys() if key != "_changed"]

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name != "_changed" and name not in self._changed:
            self._changed.append(name)

    @validator("wiki_domain")
    def validate_wiki_domain(cls, v):
        pattern = r"^(?!-)[A-Za-z0-9.-]{1,63}(?<!-)\.[A-Za-z]{2,}$"
        assert re.match(pattern, v), "The wiki domain is not valid."
        return v

    def has_changed(self, name):
        return name in self._changed

    @property
    def changed(self):
        return self._changed


params = Params()
