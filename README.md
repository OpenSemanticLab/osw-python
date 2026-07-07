[![PyPI-Server](https://img.shields.io/pypi/v/osw.svg)](https://pypi.org/project/osw/)
[![DOI](https://zenodo.org/badge/458130867.svg)](https://zenodo.org/badge/latestdoi/458130867)
[![Codecov](https://codecov.io/gh/OpenSemanticLab/osw-python/graph/badge.svg)](https://codecov.io/gh/OpenSemanticLab/osw-python)
[![docs](https://img.shields.io/badge/docs-online-blue)](https://opensemanticlab.github.io/osw-python/)
![license](https://img.shields.io/github/license/OpenSemanticLab/osw-python.svg)

# osw

Python toolset for data processing, queries, wikicode generation and page
manipulation within [OpenSemanticLab](https://github.com/OpenSemanticLab).

Work with OpenSemanticLab instances the way you work with Python objects:
load pages as typed pydantic entities, query with semantic search, generate
models from the schemas stored in the wiki, and write changes back.

**Documentation: <https://opensemanticlab.github.io/osw-python/>**

## Installation

```bash
pip install osw
```

Optional extras (`osw[wikitext]`, `osw[DB]`, `osw[S3]`, `osw[dataimport]`,
`osw[UI]`, `osw[all]`) are described in the
[Get Started guide](https://opensemanticlab.github.io/osw-python/get-started/).

## Quickstart

```python
from osw.express import OswExpress

osw = OswExpress(domain="wiki-dev.open-semantic-lab.org")
instances = osw.site.semantic_search("[[Category:Item]]")
print(instances)
```

More runnable scripts live in [examples/](examples/), and the
[Basics tutorial](docs/tutorials/basics.ipynb) walks through the
OpenSemanticLab data model.

## Contributing

Contributions are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md).
Development setup, checks and tests are one command each: `make install`,
`make check`, `make test`.

## Related projects

General features for object-oriented interaction with knowledge graphs live
in the standalone package [oold-python](https://github.com/OO-LD/oold-python).

## License

AGPL-3.0-or-later, see [LICENSE.txt](LICENSE.txt).
