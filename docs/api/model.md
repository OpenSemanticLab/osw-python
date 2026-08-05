# Model

The data model is generated from the JSON schemas of the wiki. The core
model is maintained in
[opensemantic.core-python](https://github.com/OpenSemanticWorld-Packages/opensemantic.core-python/blob/main/src/opensemantic/core/v1/_model.py)
and extended dynamically at runtime via `OSW.fetch_schema`.
