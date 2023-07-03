import re
from typing import Dict, List, Optional, Union

from pydantic import validator

from osw.model.static import OswBaseModel


# Classes
class RegExPatternExtended(OswBaseModel):
    """A class that extends the re.Pattern class with additional attributes.

    Example
    -------
    Definition
    >>> pattern = RegExPatternExtended(
    >>>     description="File page full page title (new format) to label",
    >>>     pattern=r"File:(OS[WL]{1}[[a-f0-9]{32})"
    >>>     "(\\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
    >>>     group_keys=["Label", "Suffix(es)"],  # ["OSW-ID", "Suffix(es)"]
    >>>     example_str="File:OSW11a53cdfbdc24524bf8ac435cbf65d9d.svg",
    >>>     expected_groups=["OSW11a53cdfbdc24524bf8ac435cbf65d9d", ".svg"],
    >>> )
    Usage
    >>> some_str = pattern.example_str
    >>> match = pattern.match(some_str)
    >>> label = match.groups["label"]
    >>> suffix = match.groups["Suffix(es)"]
    Testing
    >>> pattern.test_pattern()


    Resources
    ---------
    https://regex101.com/
    """

    pattern: Union[str, re.Pattern]
    """The regular expression pattern. Can be a string or a compiled pattern."""
    description: str
    """A (unique!) description of the pattern. This is used as a key in a dictionary
    containing all patterns and acting as a library."""
    group_keys: List[str]
    """A list of keys that can be used to access the match groups in the match
    result. The number of keys must match the number of match groups in the pattern.
    So the first key (list index 0) will be used to access the first match group
    (index 1!)."""
    example_str: Optional[str]
    """An example string that can be used to test the pattern."""
    expected_groups: Optional[List[str]]
    """A list strings that are expected in the example_match.groups.values(). This is
    used to test the pattern by asserting list(self.example_match.groups.values()) ==
    self.expected_groups"""

    def __init__(self, **data):
        super().__init__(**data)
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)

    def match(self, string: str) -> "MatchResult":
        """Return the match result of the given string and the pattern."""
        return MatchResult(match=re.match(self.pattern, string), pattern=self)

    @property
    def example_match(self) -> "MatchResult":
        """Return the match result of the example string and the pattern."""
        return self.match(string=self.example_str)

    @validator("group_keys")
    def validate_group_keys(cls, group_keys, values) -> List[str]:
        """Validate that the number of group keys matches the number of match groups,
        defined in the pattern."""
        pattern = values.get("pattern")
        group_count = count_match_groups(pattern)
        if len(group_keys) != group_count:
            raise ValueError(
                f"The number of group keys ({len(group_keys)}) does not match "
                f"the number of match groups ({group_count})."
            )
        return group_keys

    def test_pattern(self) -> bool:
        """Test the pattern by asserting self.example_match.groups.values()) ==
        self.expected_groups"""
        if list(self.example_match.groups.values()) == self.expected_groups:
            return True
        else:
            return False

    class Config:
        arbitrary_types_allowed = True


class MatchResult(OswBaseModel):
    match: Union[re.Match, None]
    pattern: Union[RegExPatternExtended, None]

    @property
    def groups(self):
        """Return a dictionary representation of the object, enabling accessing the
        match groups by key (as defined in RegExPatternExtended)."""
        if self.match is None or self.pattern is None:
            return None  # []
        keys = self.pattern.group_keys
        return {
            key: get_match_group_by_key(match_result=self, group_key=key)
            for key in keys
        }

    class Config:
        arbitrary_types_allowed = True


# Functions
def count_match_groups(pattern: Union[str, re.Pattern]):
    """Counts the number of match groups in a regular expression pattern.

    Parameters
    ----------
    pattern:
        The regular expression pattern.

    Returns
    -------
    group_count:
        The number of match groups in the pattern.

    Examples
    --------
    >>> pat = r"(\\d+)(\\w+)\\((\\d+)\\)"
    >>> grp_cnt = count_match_groups(pattern)
    >>> print(f"Number of match groups: {group_count}")
    """
    if isinstance(pattern, re.Pattern):
        pattern = pattern.pattern
    # Remove escaped parentheses from the pattern
    pattern = re.sub(r"\\[()]", "", pattern)

    # Find all opening and closing parentheses
    open_brackets = re.findall(r"\(", pattern)
    close_brackets = re.findall(r"\)", pattern)

    # Count the number of valid match groups
    group_count = 0
    unmatched_brackets = 0

    for _ in open_brackets:
        unmatched_brackets += 1

    for _ in close_brackets:
        if unmatched_brackets > 0:
            group_count += 1
            unmatched_brackets -= 1

    return group_count


def match_regex_patterns(
    patterns: Union[RegExPatternExtended, List[RegExPatternExtended]],
    strings: Union[str, List[str]],
    stop_at_first_match: bool = False,
) -> Dict[str, List[MatchResult]]:
    """Match a list of strings against a list of regular expression patterns. If
    stop_at_first_match is True, the function will stop matching a string as soon as it
    finds a match."""
    if isinstance(patterns, RegExPatternExtended):
        patterns = [patterns]
    if isinstance(strings, str):
        strings = [strings]
    matching_results = dict()
    for k, string in enumerate(strings):
        string_matched = False
        matching_results[string] = list()
        for i, pattern in enumerate(patterns):
            match = re.match(pattern.pattern, string)
            if match is not None:
                string_matched = True
                matching_results[string].append(
                    MatchResult(match=match, pattern=pattern)
                )
                if stop_at_first_match is True:
                    break
        if string_matched is False:
            matching_results[string].append(MatchResult(match=None, pattern=None))
    return matching_results


def match_first_regex_pattern(
    patterns: Union[RegExPatternExtended, List[RegExPatternExtended]],
    strings: Union[str, List[str]],
) -> List[MatchResult]:
    """Match a list of strings against a list of regular expression patterns. Return
    the first match for each string."""
    if isinstance(patterns, RegExPatternExtended):
        patterns = [patterns]
    if isinstance(strings, str):
        strings = [strings]
    matching_results = match_regex_patterns(patterns, strings, stop_at_first_match=True)
    return [matching_results[string][0] for string in strings]


def get_match_group_by_key(
    match_result: MatchResult, group_key: str
) -> Union[str, None]:
    """Get the value of a named group in a match result."""
    if match_result.match is None:
        return None
    if group_key not in match_result.pattern.group_keys:
        raise ValueError(f"Group '{group_key}' not found in pattern.")
    # +1 is very important here, because the first group is the whole match
    group_index = match_result.pattern.group_keys.index(group_key) + 1
    return match_result.match.group(group_index)


def test_regex_pattern(
    patterns: Union[
        str, List[str], dict, RegExPatternExtended, List[RegExPatternExtended]
    ],
    strings: List[str],
) -> dict:
    """Tests one or a list of regular expression patterns against a list of strings.
    Returns a dictionary with the results. The first pattern is evaluated first,
    and every following pattern is evaluated regarding the additional matches found.

    Parameters
    ----------
    patterns:
        A regular expression pattern string, a list of such strings or a dictionary
        as in osw.data_import_utility.REGEX_PATTERNS
    strings:
        A list of strings to test the patterns against.

    Returns
    -------

    """
    if isinstance(patterns, str):
        patterns = [
            RegExPatternExtended(
                pattern=patterns,
                description="No description",
                group_keys=[],
            )
        ]
    if isinstance(patterns, list):
        if isinstance(patterns[0], str):
            patterns = [
                RegExPatternExtended(
                    pattern=pattern,
                    description="No description",
                    group_keys=[],
                )
                for pattern in patterns
            ]
    if isinstance(patterns, dict):
        patterns = [
            RegExPatternExtended(
                pattern=val["Pattern"],
                description=key,
                group_keys=val["Groups"],
                example_str=val.get("Example string", None),
            )
            for key, val in patterns.items()
        ]
    matching_results = list()
    for i, pattern in enumerate(patterns):
        result = {
            "Pattern": pattern.pattern,
            "Matching strings": [],
            "Match objects": [],
            "No match": [],
            "Pattern description": pattern.description,
            "Group keys": pattern.group_keys,
        }
        for string in strings:
            match = re.match(pattern.pattern, string)
            match_result = MatchResult(match=match, pattern=pattern)
            if match is None:
                result["No match"].append(string)
            else:
                result["Matching strings"].append(string)
                result["Match objects"].append(match_result)
        result["Coverage per pattern"] = len(result["Matching strings"]) / len(strings)
        matching_results.append(result)

    coverage = dict()
    former_matches = list()
    for i, pattern in enumerate(patterns):
        if pattern.description != "No description":
            key = pattern.description
        else:
            key = i
        previously_unmatched = list(
            set(matching_results[i]["Matching strings"]) - set(former_matches)
        )
        coverage[key] = {
            "Pattern": pattern,
            "Pattern description": pattern.description,
            "Group keys": pattern.group_keys,
            "Matching strings": matching_results[i]["Matching strings"],
            "Matches, groups": [
                [group for group in match_result.match.groups()]
                for match_result in matching_results[i]["Match objects"]
            ],
            "Additional matches": previously_unmatched,
            "Additional matches, groups": [
                [group for group in match_result.match.groups()]
                for match_result in matching_results[i]["Match objects"]
                if match_result.match.string in previously_unmatched
            ],
            "Additional coverage": len(previously_unmatched) / len(strings),
            "Coverage per pattern": matching_results[i]["Coverage per pattern"],
            "Cumulative coverage": (len(former_matches) + len(previously_unmatched))
            / len(strings),
        }
        former_matches.extend(previously_unmatched)

    coverage["Accumulative coverage"] = sum(
        [len(result["Matching strings"]) for result in matching_results]
    ) / len(strings)
    total_coverage = len(former_matches) / len(strings)
    coverage["Total coverage"] = total_coverage
    coverage["Not covered"] = 1 - total_coverage
    coverage["Unmatched strings"] = list(set(strings) - set(former_matches))

    return {"Results of regex matching": matching_results, "Coverage": coverage}
