# Physical Quantities

Table of Contents

- [Physical Quantities](#physical-quantities)
  - [Status Quantities.ipynb](#status-quantitiesipynb)
  - [Status utils.py](#status-utilspy)
  - [Bug fixes](#bug-fixes)
  - [OSW Connector](#osw-connector)

## Status Quantities.ipynb

1. declare functions
     - passed
2. fetch data and store into json
     - passed
3. analyse wikidata
     - passed
4. create dict dbpedia -> wikidata
     - review qwdict
5. merge qudt and wikidata hierarchy
     - review -> manual corrections failed (comment out)
6. create wiki code
     - passed

## Status utils.py

1. dict_to_json
     - passed
2. json_to_dict
     - passed

## Bug fixes

- Check Qudt Quantity fetching
- Currency fetch necessary?

## OSW Connector

- Mapping merged dict to OSW schema as pydantic class

  - see  `example/store_entity.py`
  - load schema: `example/update_quantities.py`
  - create instanaces
  - upload to OSW

- Testings from Python 3.9 to 3.11  of osw python package
