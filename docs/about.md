# About

**osw-python** is the Python toolset for
[OpenSemanticLab](https://github.com/OpenSemanticLab): data processing,
semantic queries, wikicode generation and page manipulation, all against the
knowledge graph of an OpenSemanticLab / OpenSemanticWorld instance.

[![PyPI-Server](https://img.shields.io/pypi/v/osw.svg)](https://pypi.org/project/osw/)
[![DOI](https://zenodo.org/badge/458130867.svg)](https://zenodo.org/badge/latestdoi/458130867)
[![Codecov](https://codecov.io/gh/OpenSemanticLab/osw-python/graph/badge.svg)](https://codecov.io/gh/OpenSemanticLab/osw-python)
[![License](https://img.shields.io/github/license/OpenSemanticLab/osw-python.svg)](https://github.com/OpenSemanticLab/osw-python/blob/main/LICENSE.txt)

## Why osw-python?

- **Typed entities** - pages are loaded as pydantic models generated from
  the JSON schemas stored in the wiki itself
- **Semantic queries** - run semantic search and SPARQL queries from Python
- **Full page control** - read and write structured data, wikitext and
  files on any page slot
- **Controller pattern** - attach runtime behavior (databases, S3 stores,
  file handling) to entities without polluting the data model
- **Express mode** - one-liner site access with credential handling built in

General features for object-oriented interaction with knowledge graphs live
in the standalone package [oold-python](https://github.com/OO-LD/oold-python),
which osw-python builds on.

## Ecosystem

| Project | Role |
| ------- | ---- |
| [OpenSemanticLab](https://github.com/OpenSemanticLab) | The platform osw-python talks to |
| [oold-python](https://github.com/OO-LD/oold-python) | Object-oriented linked data foundation |
| [opensemantic.core](https://github.com/OpenSemanticWorld-Packages/opensemantic.core-python) | Generated core data model |

## License

AGPL-3.0-or-later, see
[LICENSE.txt](https://github.com/OpenSemanticLab/osw-python/blob/main/LICENSE.txt).
