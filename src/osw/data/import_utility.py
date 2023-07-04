import copy
import re
import uuid as uuid_module
import warnings
from pathlib import Path
from typing import Any, Callable, List, Optional, Union

import deepl
import numpy as np
from geopy import Nominatim
from jsonpath_ng import ext as jp

from osw import wiki_tools as wt
from osw.data.mining import RegExPatternExtended
from osw.model import entity as model
from osw.wtsite import WtSite

# Constants
PACKAGE_ROOT_PATH = Path(__file__).parents[2]
CREDENTIALS_FILE_PATH_DEFAULT = PACKAGE_ROOT_PATH / "examples" / "accounts.pwd.yaml"
ENABLE_SORTING = True
REGEX_PATTERN: dict[str, Union[str, dict[str, str]]] = {
    "SAP OU number and name from DN": {
        "Pattern": r"CN=(.+)([0-9]{10})-(.+),OU=Abteilungen",
        "Groups": {2: "SAP OU number", 3: "SAP OU name"},
    },
    "Location name from DN": {
        "Pattern": r"CN=[A-Za-z]+-(\d+)_L_([^_]+),OU=Standorte",
        "Groups": {1: "SAP institute number", 2: "Location name"},
    },
    "Location/Site parts from DN": {
        "Pattern": r"CN=[A-Za-z]+-(\d+)_L_(([^_^ ^-]+)-([^_^ ]+) (\d+)),OU=Standorte",
        "Groups": {
            1: "SAP institute number",
            2: "Site name",
            3: "City",
            4: "Street",
            5: "House number",
        },
    },
    "UUID from full page title": {
        "Pattern": r"([A-Za-z]+):([A-Z]+)([a-z\d\-]+)",
        "Groups": {1: "Namespace", 2: "Prefix", 3: "UUID"},
    },
}
REGEX_PATTERN_LIST = [
    RegExPatternExtended(
        description="SAP OU number and name from DN",
        pattern=r"CN=(.+)([0-9]{10})-(.+),OU=Abteilungen",
        group_keys=["Something", "SAP OU number", "SAP OU name"],
    ),
    RegExPatternExtended(
        description="Location name from DN",
        pattern=r"CN=[A-Za-z]+\-(\d+)_L_([^_]+),OU=Standorte",
        group_keys=["SAP institute number", "Location name"],
    ),
    RegExPatternExtended(
        description="Location/Site parts from DN",
        pattern=r"CN=[A-Za-z]+\-(\d+)_L_(([^_^ ^-]+)-([^_^ ]+) (\d+))," r"OU=Standorte",
        group_keys=[
            "SAP institute number",
            "Site name",
            "City",
            "Street",
            "House number",
        ],
    ),
    RegExPatternExtended(
        description="UUID from full page title",
        pattern=r"([A-Za-z]+):([A-Z]+)([a-z\d\-]+)",
        group_keys=["Namespace", "Prefix", "UUID"],
    ),
]
REGEX_PATTERN = {rep.description: rep.dict() for rep in REGEX_PATTERN_LIST}
REGEX_PATTERN_LIB = {rep.description: rep for rep in REGEX_PATTERN_LIST}


# Classes
class HelperModel(model.OswBaseModel):
    # Custom attributes
    attributes_transformed: bool = False
    references_transformed: bool = False
    casted_instance: Any = None
    full_page_title: Optional[str]

    def transform_attributes(self, dd: dict) -> bool:
        if not self.attributes_transformed:
            self.full_page_title = uuid_to_full_page_title(uuid=uuid_module.uuid4())
            # All set successfully
            self.attributes_transformed = True
        return True

    def transform_references(self, dd: dict) -> bool:
        if not self.attributes_transformed:
            self.transform_attributes(dd)
        if not self.references_transformed:
            # Test casting
            superclass = self.__class__.__bases__[0]
            self.casted_instance = self.cast_none_to_default(cls=superclass)
            # All set successfully
            self.references_transformed = True
        return True

    def cast_to_superclass(self, dd):
        if not self.references_transformed:
            self.transform_references(dd)
        else:
            superclass = self.__class__.__bases__[0]
            self.casted_instance = self.cast_none_to_default(cls=superclass)
        return True


# Functions
def transform_attributes_and_merge(
    ent: dict, ent_as_dict: dict, sel_cls, inplace: bool = True
) -> dict:
    """Merge entities of a selected class within a dictionary of entities

    Parameters
    ----------
    ent
        Dictionary of entities
    ent_as_dict
        Dictionary of entities as dictionary
    sel_cls
        Selected class
    inplace
        Whether to transform_attributes the entities inplace

    Returns
    -------

    """
    if not inplace:
        ent = copy.deepcopy(ent)
        ent_as_dict = copy.deepcopy(ent_as_dict)
    ent, ent_as_dict = loop_and_call_method(
        entities=ent,
        method_name="transform_attributes",
        method_arg=ent_as_dict,
        inplace=True,
    ).values()
    if "sorted" in ent_as_dict.keys():
        sorted_ = ent_as_dict["sorted"]
    else:
        sorted_ = False
    cls_type_str = str(sel_cls.__fields__["type"].default)

    # Merge entries with the same name / uuid
    entities_copy = copy.deepcopy(ent)  # Copy to loop over
    del_keys = list()
    for ent_k, ent_v in entities_copy.items():
        if isinstance(ent_v, sel_cls) and ent_k not in del_keys:
            ent_uuid = ent_v.uuid
            for other_k, other_v in entities_copy.items():
                if (
                    isinstance(other_v, sel_cls)
                    and ent_k != other_k
                    and ent_uuid == other_v.uuid
                    and other_k not in del_keys
                ):
                    merge_res = merge_instances(ent_v, other_v)
                    # Overwrite with merge result
                    ent[ent_k] = merge_res
                    if sorted_:
                        if cls_type_str not in ent_as_dict.keys():
                            ent_as_dict[cls_type_str] = {ent_k: {"jsondata": {}}}
                        if ent_k not in ent_as_dict[cls_type_str].keys():
                            ent_as_dict[cls_type_str][ent_k] = {"jsondata": {}}
                        ent_as_dict[cls_type_str][ent_k]["jsondata"] = merge_res.dict()
                        del ent_as_dict[cls_type_str][other_k]
                    else:
                        ent_as_dict[ent_k]["jsondata"] = merge_res.dict()
                        del ent_as_dict[other_k]
                    del ent[other_k]
                    del_keys.append(other_k)
    print(f"Merge operation complete. Deleted keys: {del_keys}")
    return {"entities": ent, "entities_as_dict": ent_as_dict}


def get_uuid_from_object_via_type(obj: Any) -> Union[uuid_module.UUID, None]:
    """Get UUID from object via type. THis function assumes that the input object
    'obj' is either a dictionary or an instance of a OswBaseModel that specifies its
    type as a string or a list of strings of the full page title format."""
    # if isinstance(obj, model.OswBaseModel):
    #     type_ = getattr(obj, "type", None)
    if isinstance(obj, dict):
        type_ = obj.get("type", None)
    else:
        type_ = getattr(obj, "type", None)
    if type_ is not None:
        # if isinstance(type_, str):
        #     type_str = type_
        if isinstance(type_, list):
            type_str = str(type_[0])
        else:
            type_str = str(type_)
        match = re.match(
            pattern=REGEX_PATTERN["UUID from full page title"]["Pattern"],
            string=type_str,
        )
        uuid_str = match.group(3)
        return uuid_module.UUID(uuid_str)
    else:
        return None


def get_lang_specific_label(label: list, lang: str) -> Union[str, None]:
    """Get the label in a specific language from a list of labels"""
    for ele in label:
        if ele["lang"] == model.LangCode(lang):
            return ele["text"]
    return None


def get_coordinates(address):
    """Get the coordinates of an address, using the Nominatim API"""
    geolocator = Nominatim(user_agent="myapplication")
    location = geolocator.geocode(address)
    return location.latitude, location.longitude


def get_one_or_more_element(inp: list):
    if len(inp) == 1:
        return inp[0]
    else:
        return inp


def unique_elements_or_none(seq: list):
    """Returns a list of the unique elements in 'seq' while preserving order.
    Taken from https://stackoverflow.com/a/480227
    """
    seen = set()
    seen_add = seen.add
    result = [x for x in seq if not (x in seen or seen_add(x))]
    if len(result) == 0:
        return None
    return result


def isclass(obj, cls):
    """Check if an object is an instance of a class or a subclass thereof.

    Parameters
    ----------
    obj
        Object to check.
    cls
        Class to check against.

    Returns
    -------
    result:
        True if obj is an instance of cls or a subclass thereof, False otherwise.
    """

    if isinstance(obj, cls):
        return True
    else:
        if isinstance(obj, dict):
            obj_type = obj.get("type")
        else:
            obj_type = getattr(obj, "type", None)
        cls_type = cls.__fields__["type"].default
        if isinstance(obj_type, list):
            obj_type.sort()
        if isinstance(cls_type, list):
            cls_type.sort()
        if obj_type == cls_type and obj_type is not None:
            return True
        return False


def flatten_list(nested_list):
    """Recursively flattens a nested list.

    Parameters
    ----------
    nested_list:
        Nested list to flatten.

    Returns
    -------
    flattened_list:
        Flattened list.

    Source
    ------
    https://www.geeksforgeeks.org/
    python-program-to-flatten-a-nested-list-using-recursion/
    """
    # check if list is empty
    if not (bool(nested_list)):
        return nested_list
    # to check instance of list is empty or not
    if isinstance(nested_list[0], list):
        # call function with sublist as argument
        return flatten_list(*nested_list[:1]) + flatten_list(nested_list[1:])
    # call function with sublist as argument
    flattened_list = nested_list[:1] + flatten_list(nested_list[1:])
    return flattened_list


def jsonpath_search_and_return_list_simple(
    jp_str: str, val_key: str, search_tar: dict
) -> Union[list, None]:
    jp_parse = jp.parse(path=jp_str)
    result = jp_parse.find(search_tar)
    list_ = []
    if result:
        for res in result:
            list_.append(res.value[val_key])
    return list_


def jsonpath_search_and_return_list(
    jp_str: str, val_key: str, search_tar: dict, class_to_match=None
) -> Union[list, None]:
    """

    Parameters
    ----------
    jp_str:
        The jsonpath string to search for
    val_key:
        The key of the value (of the search results) to be returned in a list
    search_tar:
        The dictionary to search in with jsonpath
    class_to_match:
        The class to match with the search results. Specifying this argument,
        reduces the search space dramatically and thus speeds up the search.

    Returns
    -------
    result:
        List of values with key 'val_key', matching the jsonpath string 'jp_str'
        within the 'search_tar' dictionary

    """
    jp_parse = jp.parse(path=jp_str)
    if search_tar.get("sorted") is not None:
        sorted_ = search_tar["sorted"]
    else:
        sorted_ = False
    if sorted_ and class_to_match:
        # See definition in loop_and_call_method with argument 'sorted'
        try:
            cls_type = class_to_match.__fields__["type"].default
            # Search in a dramatically reduced number of entries
            result = jp_parse.find(search_tar[str(cls_type)])
        except Exception as e:
            warnings.warn(
                f"jsonpath_search_and_return_list() threw and " f"exception:\n{str(e)}"
            )
            result = jp_parse.find(search_tar)
    else:
        result = jp_parse.find(search_tar)
    list_ = []
    if result:
        for res in result:
            res_type = res.value["type"]
            res_type.sort()
            if class_to_match is None:
                list_.append(res.value[val_key])
            elif isclass(res.value, class_to_match):
                list_.append(res.value[val_key])
    return list(set(flatten_list(list_)))


def camel_case(string, splitter: str = "\\s"):
    """Converts a string to camel case, by splitting it at spaces and capitalizing
    the first letter of each part, but the first.

    Parameters
    ----------
    string:
        String to convert to camel case.
    splitter:
        Regular expression string to split the string at. Default is any whitespace.

    Returns
    -------
    result:
        Camel case string.
    """
    if not string:
        return string
    parts = re.split(pattern=splitter, string=string)
    for i, part in enumerate(parts):
        parts[i] = part.capitalize()
    parts[0] = parts[0].lower()
    return "".join(parts)


def nan_empty_or_none(inp: Any) -> bool:
    """Checks if the input is None, an empty string, or a string "nan".

    Parameters
    ----------
    inp:
        Input to check.

    Returns
    -------
    result
    """
    if isinstance(inp, str):
        if inp == "nan" or inp == "":
            return True
        return False
    elif isinstance(inp, list):
        for ele in inp:
            if not nan_empty_or_none(ele):
                return False
        return True
    elif inp is None:
        return True
    else:
        try:
            if np.isnan(inp):
                return True
        except Exception as e:
            _ = e  # Bad catch
    return False


def regex_match_list(pattern: str, list_of_strings: List[str]) -> List[str]:
    """Returns a subset of the 'list_of_strings' that matched the regex 'pattern'.

    Parameters
    ----------
    pattern
    list_of_strings

    Returns
    -------
    matches:
        A lost of strings that matched the regex 'pattern'.
    """
    matches = []
    for string in list_of_strings:
        if re.match(pattern=pattern, string=string):
            matches.append(string)
    return matches


def sort_dict_of_entities_as_dict_by_type(
    entities_as_dict: dict[str, dict],
    inplace: bool = True,
    sublevel_key: str = "jsondata",
) -> dict:
    """

    Parameters
    ----------
    entities_as_dict:
        Dictionary of entities as dictionaries.
    inplace:
        If True, the input dictionary is sorted in place. If False, a copy is made.
    sublevel_key:
        The key of the sublevel in the entities_as_dict dictionary.

    Returns
    -------
    entities_as_dict:
        The sorted dictionary of entities as dictionaries.
    """
    if not inplace:
        entities_as_dict = copy.deepcopy(entities_as_dict)
    if "sorted" in entities_as_dict.keys():
        sorted_ = entities_as_dict["sorted"]
    else:
        sorted_ = False
    if not sorted_:  # Sort
        entities_as_dict_sorted = {}
        for key, val in entities_as_dict.items():
            val_type = str(val[sublevel_key]["type"])
            if val_type not in entities_as_dict_sorted.keys():
                entities_as_dict_sorted[val_type] = {}
            entities_as_dict_sorted[val_type][key] = val
        sorted_ = True
        entities_as_dict = entities_as_dict_sorted

    entities_as_dict["sorted"] = sorted_
    return entities_as_dict


def loop_and_call_method(
    entities: dict,
    method_name: str,
    method_arg: dict,
    inplace: bool = True,
    sort: bool = None,
    sublevel_key: str = "jsondata",
) -> dict:
    """Loops through dict 'entities', applies 'method' with 'method_arg' (also a
    dict, which is looped through) and either writes the result to the original dict
    ('inplace') or to a copy, which is then returned.

    Parameters
    ----------
    entities:
        Dictionary of entities.
    method_name:
        Name of the method to be called on each entity.
    method_arg:
        Positional argument passed to the method.
    inplace:
        If True, the method is applied to the original dict. If False, a copy is made.
    sort:
        If True, entities in 'method_arg' will be sorted according to attribute /
        dictionary key 'type' prio to being passed to the method. Returned
        'method_arg' will also contain the sorted structure.
    sublevel_key:
        String to be used on the dictionary sublevel.

    Returns
    -------
    result:
        Dictionary containing a dictionary of entities and a dictionary of entities
        as dict.
    """
    if sort is None:
        sort = ENABLE_SORTING
    if not inplace:
        entities = copy.deepcopy(entities)
        method_arg = copy.deepcopy(method_arg)
    if sort:
        method_arg = sort_dict_of_entities_as_dict_by_type(method_arg, inplace=True)
    # Loop and apply / call method
    entities_keys = copy.deepcopy(list(entities.keys()))
    for key in entities_keys:
        val = entities[key]
        method = val.__getattribute__(method_name)
        type_str = str(val.__getattribute__("type"))
        method_res = method(method_arg)
        if method_res:
            if key in entities.keys():
                entities[key] = val
            if sort and key in method_arg[type_str].keys():
                method_arg[type_str][key][sublevel_key] = val.dict()
            if not sort and key in method_arg.keys():
                method_arg[key][sublevel_key] = val.dict()
        else:
            if key in entities.keys():
                del entities[key]
            if sort and key in method_arg[type_str].keys():
                del method_arg[type_str][key]
            if not sort and key in method_arg.keys():
                del method_arg[key]
    return {"entities": entities, "method_arg": method_arg}


def merge_dicts(one: dict, other: dict) -> dict:
    """Merges two dictionaries, with the dictionary 'other' being the dominant
    dictionary, overwriting attributes of 'one'.
    """
    new_dict = dict()
    self_dict = one
    other_dict = other
    for key, self_val in self_dict.items():
        other_val = other_dict[key]
        if self_val == other_val:
            new_dict[key] = other_val
        else:
            if isinstance(self_val, list):
                self_set = set(self_val)
                other_set = set(other_val)
                in_other_but_not_in_self = other_set - self_set
                new_dict[key] = self_val + list(in_other_but_not_in_self)
            else:
                new_dict[key] = other_val
    return new_dict


def merge_instances(one, other, cls=None):
    """Merges two instances of any type (provided the class has a method 'dict()')
    with the instance 'other' being the dominant instance, overwriting attributes of
    'one'. The class is derived from 'one' if not specified in 'cls'. The merge is
    shallow, i.e. only the top level of the instances is merged.
    """
    if cls is None:
        cls = one.__class__
    new_dict = merge_dicts(one=one.dict(), other=other.dict())
    # todo: make deep merge available
    return cls(**new_dict)


def list_of_entities_to_dict_of_entities(
    list_of_entities: list,
    key_factory: Callable = None,
    key_factory_kwargs: dict = None,
    pass_entity_as_arg: bool = False,
) -> dict:
    """Converts a list of entities to a dictionary, with the keys being the
    'uuid' of the entities.

    Parameters
    ----------
    list_of_entities:
    key_factory:
        Function that takes kwargs as input and returns a key for the dictionary.
    key_factory_kwargs:
        Dictionary of keyword arguments to be passed to the key_factory function.
    pass_entity_as_arg:
        If True, the entity will be passed as an argument to the key_factory function.

    Returns
    -------
    dict_of_entities:
        Dictionary of entities.
    """
    dict_of_entities = {}
    for entity in list_of_entities:
        if getattr(entity, "uuid", None) is not None and key_factory is None:
            key = entity.uuid
        elif getattr(entity, "uuid", None) is None and key_factory is None:
            key = uuid_module.uuid4()
        elif key_factory is not None and key_factory_kwargs is None:
            if pass_entity_as_arg:
                key = key_factory(entity)
            else:
                key = key_factory()
        elif key_factory is not None and key_factory_kwargs is not None:
            if pass_entity_as_arg:
                key = key_factory(entity, **key_factory_kwargs)
            else:
                key = key_factory(**key_factory_kwargs)
        else:
            key = uuid_module.uuid4()
        dict_of_entities[str(key)] = entity
    return dict_of_entities


def insert_sublevel_to_dict(inp: dict, sublevel_key: str) -> dict:
    """Inserts a sublevel to a dictionary, with the key of the sublevel being
    'sublevel_key'."""
    result = {}
    for key, val in inp.items():
        result[key] = {sublevel_key: val}
    return result


def make_dict_jsonpath_compatible(inp: dict, sublevel_key: str = "jsondata") -> dict:
    """Makes a dictionary compatible with jsonpath, by inserting a sublevel with
    the key 'sublevel_key'."""
    result = {}
    for key, val in inp.items():
        # Try to access method 'dict' of the value, if it exists, use it, otherwise
        res = getattr(val, "dict", None)
        if res is not None:
            result[key] = {sublevel_key: val.dict()}
        else:
            result[key] = {sublevel_key: val}
    return result


def create_page_name_from_label(label: str) -> str:
    """Creates a page name from a label, by splitting the label at whitespaces,
    dashes, underscores, dots and slashes and capitalizing the first letter of
    each split."""
    splits = re.split(pattern="[\\s\\-\\_\\./]+", string=label)
    page_name = "".join([ele.capitalize() for ele in splits])
    return page_name


def get_entities_from_osw(
    category_to_search: Union[str, uuid_module.UUID],
    model_to_cast_to,
    credentials_fp,
    debug: bool = False,
) -> list:
    """Gets entities from OSW, based on a category. The category can be specified by
    a string or a UUID. The entities are cast to the model specified by
    'model_to_cast_to'.

    Parameters
    ----------
    category_to_search:
        Category to search for.
    model_to_cast_to:
        Model to cast the entities to.
    credentials_fp:
        Filepath to the credentials file, used to access the OSW instance.
    debug:
        If True, prints debug information.

    Returns
    -------
    entities_from_osw:
        List of entities from OSW.
    """
    if isinstance(category_to_search, str):
        category_uuid = category_to_search.split("OSW")[-1]
    else:  # elif isinstance(category_to_search, uuid_module.UUID):
        category_uuid = str(category_to_search)
    domains, accounts = wt.read_domains_from_credentials_file(credentials_fp)
    domain = domains[3]
    wtsite_obj = WtSite.from_domain(
        domain=domain, password_file="", credentials=accounts[domain]
    )
    entities_from_osw = []
    if debug:
        print(f"Searching for instances of {category_to_search} in OSW...")
    entities = wtsite_obj.semantic_search(
        query=wt.SearchParam(
            query=f"[[HasType::Category:OSW{str(category_uuid).replace('-', '')}]]",
            debug=debug,
        )
    )
    for entity in entities:
        # entity = full page name
        page = wtsite_obj.get_WtPage(entity)
        if page.exists:
            jsondata = page.get_slot_content("jsondata")
            jsondata["full_page_title"] = entity
            entities_from_osw.append(model_to_cast_to(**jsondata))
    return entities_from_osw


def uuid_to_full_page_title(
    uuid: Union[uuid_module.UUID, str], wiki_ns: str = "Item", prefix: str = "OSW"
) -> str:
    """Converts a UUID to a full page title, by prepending the wiki namespace and
    prefix to the UUID after removing dashes."""
    return f"{wiki_ns}:{prefix}{str(uuid).replace('-', '')}"


def create_full_page_title(
    name: str, uuid_ns: uuid_module.UUID, wiki_ns: str = "Item", prefix: str = "OSW"
):
    """Creates a full page title from a name and a UUID namespace, by prepending the
    wiki namespace and prefix to the UUID after removing dashes."""
    _uuid = uuid_module.uuid5(uuid_ns, name)
    return uuid_to_full_page_title(uuid=_uuid, wiki_ns=wiki_ns, prefix=prefix)


def translate_list_with_deepl(
    seq: list, credentials_file_path: Union[str, Path] = None
) -> list:
    """Translates a list of strings with DeepL."""
    if credentials_file_path is None:
        credentials_file_path = CREDENTIALS_FILE_PATH_DEFAULT
    domains, accounts = wt.read_domains_from_credentials_file(credentials_file_path)
    domain = "api-free.deepl.com"
    auth = accounts[domain]["password"]
    translator = deepl.Translator(auth)
    return [translator.translate_text(ele, target_lang="EN-US").text for ele in seq]
