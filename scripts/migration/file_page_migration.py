"""This script is meant to help with the migration of file pages from previous
versions to the current version of the OSW (xx and above).

Draft
-----
* Query OSW file pages
* Query OSW pages containing / referencing files
* Query instances of WikiFile (Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d)
* Remove instances of WikiFile from the results of the first query
* Process the remaining pages

Notes
-----
* Work with dask for the processing (but not for the queries)

"""


if __name__ == "__main__":
    pass
