[![PyPI-Server](https://img.shields.io/pypi/v/osw.svg)](https://pypi.org/project/osw/)
[![DOI](https://zenodo.org/badge/458130867.svg)](https://zenodo.org/badge/latestdoi/458130867)
[![Coveralls](https://img.shields.io/coveralls/github/OpenSemanticLab/osw-python/main.svg)](https://coveralls.io/r/<USER>/osw)
[![Project generated with PyScaffold](https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold)](https://pyscaffold.org/)

# osw

Python toolset for data processing, queries, wikicode generation and page manipulation within OpenSemanticLab.
General features for object oriented interaction with knowledge graphs are planned to be moved to a standalone package: [oold-python](https://github.com/OpenSemanticWorld/oold-python)

## Installation
```
pip install osw
```

## Troubleshooting

### `Error: datamodel-codegen not found`
make sure datamodel-codegen is installed and included in PATH, e. g. on jupyterlab:
```
os.environ["PATH"] += os.pathsep + "/home/jovyan/.local/bin"
```

## Documentation

https://opensemanticlab.github.io/osw-python/


## Development

Dev install
```bash
pip install -e .
```

Run tests
```bash
tox -e test
```

Run integration tests (tests are skipped if login params are not provided)
```bash
tox -e test -- --wiki_domain "<osl-domain>" --wiki_username "<(bot)login>" --wiki_password "<password>" --db_username "<username>" --db_password "<password>"
```

<!-- pyscaffold-notes -->

## Note

This project has been set up using PyScaffold 4.3.1. For details and usage
information on PyScaffold see https://pyscaffold.org/.
