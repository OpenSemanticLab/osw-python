[![PyPI-Server](https://img.shields.io/pypi/v/osw.svg)](https://pypi.org/project/osw/)<!-- markdownlint-disable MD041-->
[![DOI](https://zenodo.org/badge/458130867.svg)](https://zenodo.org/badge/latestdoi/458130867)
[![Coveralls](https://img.shields.io/coveralls/github/OpenSemanticLab/osw-python/main.svg)](https://coveralls.io/r/OpenSemanticLab/osw)
[![docs](xx.xx)](https://opensemanticlab.github.io/osw-python/)
![license](https://img.shields.io/github/license/OpenSemanticLab/osw-python.svg)
<!-- [![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.
com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev) -->
[![Project generated with PyScaffold](https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold)](https://pyscaffold.org/)

# osw

Python toolset for data processing, queries, wikicode generation and page manipulation within OpenSemanticLab.

General features for object-oriented interaction with knowledge graphs are planned to be moved to a standalone package:
[oold-python](https://github.com/OpenSemanticWorld/oold-python)

## Table of Contents <!-- omit in toc -->

- [osw](#osw)
  - [Installation](#installation)
    - [Variants](#variants)
  - [Getting started](#getting-started)
  - [Troubleshooting](#troubleshooting)
    - [`Error: datamodel-codegen not found`](#error-datamodel-codegen-not-found)
    - [Tutorials](#tutorials)
  - [Development](#development)
  - [Note](#note)

## Installation

```bash
pip install osw
```

### Variants

| Variant           | Description                                                                    |
| ----------------- | ------------------------------------------------------------------------------ |
| `osw[wikitext]`   | Additional functions in `wiki_tools` to transform mediawiki markup / templates |
| `osw[DB]`         | interact with SQL databases per DatabaseController                             |
| `osw[S3]`         | Interact with S3 Stores per S3FileController                                   |
| `osw[dataimport]` | Additional tools to import data                                                |
| `osw[UI]`         | To use a helper UI to work with entity slots                                   |

To install multiple optional/extra dependencies run

```bash
pip install osw[opt1, opt2, ...]
```

To install all optional/extra dependencies run

```bash
pip install osw[all]
```

## Getting started

You can find examples in the tutorial folder, e.g. [entity creation](https://github.com/OpenSemanticLab/osw-python/blob/main/examples/create_entity.py), [entity manipulaton](https://github.com/OpenSemanticLab/osw-python/blob/main/examples/store_entity.py), [querying](https://github.com/OpenSemanticLab/osw-python/blob/main/examples/query_minimal.py), and [file downloads](https://github.com/OpenSemanticLab/osw-python/blob/main/examples/file_download_minimal.py)

## Troubleshooting

### `Error: datamodel-codegen not found`

make sure datamodel-codegen is installed and included in PATH, e. g. on jupyterlab:

```bash
os.environ["PATH"] += os.pathsep + "/home/jovyan/.local/bin"
```

### Tutorials

Tutorials can be found at [tutorials](docs/tutorials/)

- [Basics](docs/tutorials/basics.md) - a description of the data model of OpenSemanticLab and how to interact with it

## Development

Minimal `Dev` install

```bash
pip install -e .[dev,testing]
```

Complete `Dev` install

```bash
pip install -e .[all,dev,testing]
```

Activate pre-commit hooks (in git console)

```bash
pre-commit install
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
information on PyScaffold see [pyscaffold](https://pyscaffold.org/).
