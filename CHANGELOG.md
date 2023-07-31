# Changelog

## Version v0.12.0
 - rework ontology import (BREAKING, see examples/ontology_import.py)
 - add in-memory credentials in CredentialManager
 - fix: 'value is not a valid enumeration member' errors
 - improve namespace detection
 - parallelize get_page

## Version v0.11.0
 - fix code generator for Statement
 - parallelize page operations
 - add legacy file page migration script
 - refactor search function in wiki_tools
 - add file info to utils
 - refactor WtSite to work directly with CredentialManager

## Version v0.10.0
 - refactor PagePackage creation
 - add requiredExtensions, requiredPackages

## Version v0.9.0

- parallelize page operation to increase performance significantly
- improve local slot editor
- deprecate WtPage.from_domain()
- deprecate WtPage.from_credentials()
- add PagePackage import
- add utils
- add additional requirements 'dataimport', 'UI'
- reset 'setuptools' and 'pytest' versions to latest
- extend python version support to 3.11

## Version v0.8.1

- fix #18
- fix #19

## Version v0.8.0

- Restructure package package creation
- fix namespace mappings (e. g. for the SMW Property namespace)

## Version v0.7.x

- add database controller
- fix duplicated file entries in page packages

## Version v0.6.0

- add database controller

## Version v0.5.x

- Implemented an alternative cast method discriminating None values
- fix large cookie error after > 100 edits
- add support to store a list of entities
- encoding fixes

## Version v0.4.1

- fix datamodel-code-generator version to 0.15.0

## Version v0.4.0

- use editslots API
- remove None entries in json exports
- set default content for header and footer slot
- improve docs
- update examples

## Version v0.3.0

- add local slot edit feature


## Version v0.2.0

- rename OSL to OSW
- add page package feature


## Version v0.1.0

- create package
