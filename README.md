<!-- These are examples of badges you might want to add to your README:
     please update the URLs accordingly

[![Built Status](https://api.cirrus-ci.com/github/<USER>/osw.svg?branch=main)](https://cirrus-ci.com/github/<USER>/osw)
[![ReadTheDocs](https://readthedocs.org/projects/osw/badge/?version=latest)](https://osw.readthedocs.io/en/stable/)
[![Coveralls](https://img.shields.io/coveralls/github/<USER>/osw/main.svg)](https://coveralls.io/r/<USER>/osw)
[![PyPI-Server](https://img.shields.io/pypi/v/osw.svg)](https://pypi.org/project/osw/)
[![Conda-Forge](https://img.shields.io/conda/vn/conda-forge/osw.svg)](https://anaconda.org/conda-forge/osw)
[![Monthly Downloads](https://pepy.tech/badge/osw/month)](https://pepy.tech/project/osw)
[![Twitter](https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter)](https://twitter.com/osw)
-->

[![PyPI-Server](https://img.shields.io/pypi/v/osw.svg)](https://pypi.org/project/osw/)
[![DOI](https://zenodo.org/badge/458130867.svg)](https://zenodo.org/badge/latestdoi/458130867)
[![Coveralls](https://img.shields.io/coveralls/github/OpenSemanticLab/osw-python/main.svg)](https://coveralls.io/r/<USER>/osw)
[![Project generated with PyScaffold](https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold)](https://pyscaffold.org/)

# osw

> Python toolset for data processing, queries, wikicode generation and page manipulation

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

<!-- pyscaffold-notes -->

## Note

This project has been set up using PyScaffold 4.3.1. For details and usage
information on PyScaffold see https://pyscaffold.org/.
