# osw

Python toolset for data processing, queries, wikicode generation and page
manipulation within [OpenSemanticLab](https://github.com/OpenSemanticLab).

General features for object-oriented interaction with knowledge graphs are
provided by the standalone package
[oold-python](https://github.com/OO-LD/oold-python).

## Installation

```bash
pip install osw
```

### Variants

| Variant | Description |
| ------- | ----------- |
| `osw[wikitext]` | Additional functions in `wiki_tools` to transform mediawiki markup / templates |
| `osw[DB]` | Interact with SQL databases per DatabaseController |
| `osw[S3]` | Interact with S3 stores per S3FileController |
| `osw[dataimport]` | Additional tools to import data |
| `osw[UI]` | To use a helper UI to work with entity slots |

To install multiple optional/extra dependencies run

```bash
pip install osw[opt1,opt2]
```

To install all optional/extra dependencies run

```bash
pip install osw[all]
```

## Documentation

- [Tools](tools.md): collection of helper functions
- [Authentication](auth.md): credential handling
- [OSW](osw.md): the central `OSW` class
- [Model](model.md): the generated data model
- [Controller](controller.md): controller classes
- [Development](dev.md): development environment setup
