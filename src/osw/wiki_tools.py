import getpass
from typing import Dict, List, Optional, Tuple, Union

import mwclient
import yaml
from pydantic.v1 import FilePath

from osw.model.static import OswBaseModel
from osw.utils.util import parallelize

# try import functions from wikitext.py (relies on the extra dependency osw[wikitext])
try:
    from osw.utils.wikitext import create_flat_content_structure_from_wikitext  # noqa
    from osw.utils.wikitext import extend_page_list_with_recursive_dependencies  # noqa
    from osw.utils.wikitext import find_dependencies  # noqa
    from osw.utils.wikitext import find_dependencies_recursively  # noqa
    from osw.utils.wikitext import get_wikitext_from_flat_content_dict  # noqa
    from osw.utils.wikitext import get_wikitext_from_flat_content_structure  # noqa
    from osw.utils.wikitext import merge_wiki_page_text  # noqa;
    from osw.utils.wikitext import schemaJson2WikiJson  # noqa
    from osw.utils.wikitext import update_template_within_wikitext  # noqa
    from osw.utils.wikitext import wikiJson2SchemaJson  # noqa
    from osw.utils.wikitext import wikiJson2SchemaJsonRecursion  # noqa

except ImportError:
    print(
        "Hint: The extra dependency 'osw[wikitext]' "
        "is required for the full functionality of wiki_tools module."
    )


def read_domains_from_credentials_file(
    credentials_file_path: Union[str, FilePath]
) -> Tuple[List[str], Dict[str, Dict[str, str]]]:
    """Reads domains and credentials from a yaml file

    Parameters
    ----------
    credentials_file_path
        Path to the yaml file with the credentials

    Returns
    -------

    """
    with open(credentials_file_path, "r", encoding="utf-8") as stream_:
        try:
            accounts_dict = yaml.safe_load(stream_)
            domains_list = list(accounts_dict.keys())
            if len(domains_list) == 0:
                raise ValueError("No domain found in accounts.pwd.yaml!")
            return domains_list, accounts_dict
        except yaml.YAMLError as exc_:
            print(exc_)


def read_credentials_from_yaml(
    password_file: Union[str, FilePath], domain: str = None
) -> dict:
    """Reads credentials from a yaml file

    Parameters
    ----------
    password_file :
        Path to the yaml file with the credentials.
    domain:
        Domain of the OSW instance, as specifed in the yaml file.

    Returns
    -------
    credentials :
        Dictionary with the credentials, expected to
        contain keys 'username' and 'password'.
    """
    if password_file != "":
        with open(password_file, "r") as stream:
            try:
                accounts = yaml.safe_load(stream)
                if domain is not None and domain in accounts.keys():
                    domain = domain
                elif len(accounts.keys()) > 0:
                    domain = list(accounts.keys())[0]
                    if len(accounts.keys()) > 0:
                        domain = list(accounts.keys())[0]
                user = accounts[domain]["username"]
                password = accounts[domain]["password"]
            except yaml.YAMLError as exc:
                print(exc)
    else:
        user = input("Enter bot username (username@botname)")
        password = getpass.getpass("Enter bot password")
    return {"username": user, "password": password}


def create_site_object(
    domain: str, password_file: Union[str, FilePath] = "", credentials: dict = None
) -> mwclient.client.Site:
    """
    Parameters
    ----------
    domain :
        Domain of the OSW instance, as specifed in the yaml file
    password_file :
        path to file with <username>\n<password>
    credentials :
        Dictionary with the credentials (username, password)
    Returns
    -------
    site : mwclient.client.Site
        Site object from mwclient lib
    """
    domain_dict = {
        "wiki-dev": {"Address": "wiki-dev.open-semantic-lab.org"},
        "onterface": {"Address": "onterface.open-semantic-lab.org:"},
    }
    if domain in domain_dict.keys():
        domain = domain_dict[domain]["Address"]

    site = mwclient.Site(domain, path="/w/")
    if credentials is None:
        credentials = read_credentials_from_yaml(password_file, domain)
    # else:
    #     credentials = credentials
    # Login with dictionary unpacking:
    # site.login(**credentials)
    # Explicit login:
    site.login(username=credentials["username"], password=credentials["password"])
    del credentials
    return site


class SearchParam(OswBaseModel):
    """Search parameters for semantic and prefix search"""

    query: Union[str, List[str]]
    parallel: Optional[bool] = None  # is set to true if query is a list longer than 5
    debug: Optional[bool] = True
    limit: Optional[int] = 1000

    def __init__(self, **data):
        super().__init__(**data)
        if not isinstance(self.query, list):
            self.query = [self.query]
        if len(self.query) > 5 and self.parallel is None:
            self.parallel = True
        if self.parallel is None:
            self.parallel = False


def prefix_search(
    site: mwclient.client.Site, text: Union[str, SearchParam]
) -> List[str]:
    """Standard query. Equivalent to the following mediawiki API call
    api.php?action=query&list=prefixsearch&pssearch=Star Wars.

    See https://www.mediawiki.org/wiki/API:Prefixsearch for details.

    Parameters
    ----------
    site :
        Site object from mwclient lib
    text :
        Query text or instance of SearchParam

    Returns
    -------
    page_list :
        List of page titles
    """
    if not isinstance(text, SearchParam):
        query = SearchParam(query=text)
    else:
        query = text

    def prefix_search_(single_text):
        page_list = list()
        result = site.api(
            "query",
            list="prefixsearch",
            pssearch=single_text,
            pslimit=query.limit,
            format="json",
        )
        if len(result["query"]["prefixsearch"]) == 0:
            if query.debug:
                print("No results")
        else:
            for page in result["query"]["prefixsearch"]:
                title = page["title"]
                if query.debug:
                    print(title)
                page_list.append(title)
        return page_list

    if query.parallel:
        query_results = parallelize(
            func=prefix_search_, iterable=query.query, flush_at_end=query.debug
        )
    else:
        query_results = [prefix_search_(single_text=sq) for sq in query.query]

    return [item for sublist in query_results for item in sublist]
    # todo: @Simon: a list of lists of strings (sublist for each query in query list)
    #  or a list of strings (results of all queries combined)?
    #  The last option would not change the behavior of the function, but would
    # return page_list  # original return


def semantic_search(
    site: mwclient.client.Site, query: Union[str, List[str], SearchParam]
) -> List[str]:
    """Semantic query

    Parameters
    ----------
    site :
        Site object from mwclient lib
    query :
        (List of) query text(s) or instance of SearchParam

    Returns
    -------
    page_list:
        List of page titles
    """
    if not isinstance(query, SearchParam):
        query = SearchParam(query=query)

    def semantic_search_(single_query):
        page_list = list()
        single_query += f"|limit={query.limit}"
        result = site.api("ask", query=single_query, format="json")
        if len(result["query"]["results"]) == 0:
            if query.debug:
                print("Query '{}' returned no results".format(single_query))
        else:
            if query.debug:
                print(
                    "Query '{}' returned {} results".format(
                        single_query, len(result["query"]["results"])
                    )
                )
            for page in result["query"]["results"].values():
                # why do we do the following?
                if "printouts" in page:
                    title = page["fulltext"]
                    if "#" not in title and query.debug:
                        print(title)
                        # original position of "page_list.append(title)" line
                    page_list.append(title)
        return page_list

    if query.parallel:
        query_results = parallelize(
            func=semantic_search_, iterable=query.query, flush_at_end=query.debug
        )
    else:
        query_results = [semantic_search_(single_query=sq) for sq in query.query]

    return [item for sublist in query_results for item in sublist]
    # todo: @Simon: a list of lists of strings (sublist for each query in query list)
    #  or a list of strings (results of all queries combined)?
    #  The last option would not change the behavior of the function, but would
    # return page_list  # original return


def search_wiki_page(title: str, site: mwclient.client.Site):
    """Page search wrapper that adds exact match functionality with ignore-case on
    top of the  prefix_search()'s functionality.

    Parameters
    ----------
    title :
        Title of the wiki page, e.g., User:Someone1234
    site :
        Site object from mwclient lib

    Returns
    -------
    result_dict : dict
    """
    result = site.api(
        "query", list="prefixsearch", pssearch=title, pslimit=1000, format="json"
    )
    if len(result["query"]["prefixsearch"]) == 0:
        return {"Result": False, "List": list()}
    else:
        exact_match = False
        page_title_list = list()
        for page in result["query"]["prefixsearch"]:
            page_title = page["title"]
            page_title_list.append(page_title)
            if page_title.lower() == title.lower():
                exact_match = True
        result_dict = {
            "Result": True,
            "List": page_title_list,
            "Exact match": exact_match,
        }
        return result_dict


def create_or_update_wiki_page_with_template(
    title, content, site, overwrite_with_empty=False
):
    """Creates a wiki page with a template included in the content. If the page does
    already exist, the parameters within the template are update

    Parameters
    ----------
    title : str
        Title of the wiki page, e.g., User:Someone1234
    content : str
    site : mwclient.client.Site
        Site object from mwclient lib
    overwrite_with_empty : bool
        Decided whether a template parameter's value in an preexisting page is
        overwritten with an empty value

    Returns
    -------
    success : bool
    """
    search_result = search_wiki_page(title, site)
    if search_result["Result"]:
        existing_page = site.pages[title]
        existing_text = existing_page.text()
        # update the page's content (template only)
        updated_content = update_template_within_wikitext(
            text=existing_text,
            template_text=content,
            overwrite_with_empty=overwrite_with_empty,
        )
        success = create_or_overwrite_wiki_page(title, updated_content, site)
    else:
        # just create the page
        success = create_or_overwrite_wiki_page(title, content, site)
    return success


def edit_wiki_page_with_content_merge(title, new_content, site, template_name):
    """Edits an existing wiki page, while merging the passed new content with the
    content of the existing page

    Parameters
    ----------
    title : str
        Title of the wiki page, e.g., User:Someone1234
    new_content : str
    site : mwclient.client.Site
        Site object from mwclient lib
    template_name : str

    Returns
    -------
    success : bool
    """
    search_result = search_wiki_page(title, site)
    if search_result["Result"]:
        source_page = site.pages[title]
        source_page_content = source_page.text()
        # todo: test function
        new_content = merge_wiki_page_text(
            new_content, source_page_content, template_name=template_name
        )
        target_page = site.pages[title]
        target_page.edit(new_content, "[bot] update of page content")
        success = True
    else:
        success = False
    return success


def get_file_info_and_usage(
    site: mwclient.client.Site, title: Union[str, List[str], SearchParam]
) -> List[Dict[str, Union[Dict[str, str], List[str]]]]:
    """(For 'File' pages only) Get information about the file and its usage

    Parameters
    ----------
    site:
        Site object from mwclient lib.
    title:
        Title(s) of the wiki page(s) or instance of SearchParam.

    Returns
    -------
    result:
        Dictionary with page titles as keys and nested dictionary with keys 'info' and
        'usage'.

    Notes
    -----
    Query to reproduce:
        action=query
        format=json
        prop=imageinfo|fileusage
        titles=File%3AOSW857d85031d85425aa94db8b4720e84b7.png
        &iiprop=timestamp%7Cuser&fulimit=5000"

    Resources
    ---------
    Use the sandbox to design and test the queries:
    https://demo.open-semantic-lab.org/wiki/Special:ApiSandbox
    """
    if not isinstance(title, SearchParam):
        query = SearchParam(query=title, debug=False)
    else:  # SearchParam
        query = title

    def get_file_info_and_usage_(single_title):
        api_request_result = site.api(
            action="query",
            format="json",
            prop="imageinfo|fileusage",
            titles=single_title,
            iiprop="timestamp|user",
            fulimit=query.limit,
        )
        using_pages = []
        file_info = {
            "title": single_title,
            "author": "File not found or no creation logged",
            "timestamp": "File not found or no creation logged",
            "editor": [],
            "editing_timestamp": [],
        }

        if len(api_request_result["query"]["pages"]) == 0:
            if query.debug:
                print(f"Page not found: '{single_title}'!")
        else:
            image_info: List[Dict[str, str]] = []
            file_usage: List[Dict[str, Union[str, int]]] = []
            for _page_id, page_dict in api_request_result["query"]["pages"].items():
                if page_dict["title"] == single_title:
                    image_info = page_dict.get("imageinfo", [])
                    file_usage = page_dict.get("fileusage", [])
            if len(image_info) != 0:
                file_info["author"] = image_info[0]["user"]
                file_info["timestamp"] = image_info[0]["timestamp"]
                for ii in image_info:
                    file_info["editor"].append(ii["user"])
                    file_info["editing_timestamp"].append(ii["timestamp"])
            if file_usage is not None:
                for fu_page_dict in file_usage:
                    using_pages.append(fu_page_dict["title"])
            if query.debug:
                # todo: find out why this message is printed (sometimes) when using the
                #  redirect,  which messes up the Progressbar
                #  printed messages do not appear in the MessageBuffer
                print(f"File info for '{single_title}' retrieved.")
        return {"info": file_info, "usage": using_pages}

    if query.parallel:
        api_request_results = parallelize(
            func=get_file_info_and_usage_,
            iterable=query.query,
            flush_at_end=query.debug,
        )
    else:
        api_request_results = [
            get_file_info_and_usage_(single_title=st) for st in query.query
        ]

    return api_request_results


def search_redirection_sources(
    site: mwclient.client.Site, target_title: str, debug: bool = False
):
    """Returns a list of pages redirecting to the page with target_title per #REDIRECT
    [[target]] syntax

    Parameters
    ----------
    site :
        Site object from mwclient lib
    target_title :
        Title of the target wiki page
    debug:
        Whether to print debugging messages

    Returns
    -------
    page_list : list of pages redirecting to the page with target_title
    """
    page_list = []
    result = site.api("query", titles=target_title, prop="redirects", format="json")
    if len(result["query"]["pages"]) == 0:
        if debug:
            print("No results")
    else:
        for page in result["query"]["pages"]:
            if "redirects" not in result["query"]["pages"][page]:
                if debug:
                    print("No results")
            else:
                for redirecting_source in result["query"]["pages"][page]["redirects"]:
                    title = redirecting_source["title"]
                    page_list.append(title)
    return page_list


def create_or_overwrite_wiki_page(title, content, site):
    """Creates a page with the passed title and content. If the page already exists,
    the prior content is replaced with the passed content.

    Parameters
    ----------
    title : str
        Title of the wiki page, e.g., User:Someone1234
    content : str
    site : mwclient.client.Site
        Site object from mwclient lib

    Returns
    -------
    success : bool
    """
    target_page = site.pages[title]
    target_page.edit(content, "[bot] create page")
    success = True
    return success


def delete_wiki_page(title, site, reason):
    """Deletes the wiki page with the passed title, if it was found (exact match!),
    otherwise returns False

    Parameters
    ----------
    title : str
        Title of the wiki page, e.g., User:Someone1234
    site : mwclient.client.Site
        Site object from mwclient lib
    reason : str

    Returns
    -------
    success : bool
    """
    try:
        page = site.pages[title]
        page.delete(reason=reason, watch=False, unwatch=True, oldimage=False)
        success = True
    except mwclient.errors.APIError:
        success = False
    return success


def copy_wiki_page(title0, title1, site0, site1, overwrite=True):
    """

    Parameters
    ----------
    title0 : str
        Title of the source page
    title1 : str
        Title of the target page
    site0 : mwclient.client.Site
        Source site object from mwclient lib
    site1 : mwclient.client.Site
        Target site object from mwclient lib
    overwrite : bool
        Whether to overwrite existing pages at target site

    Returns
    -------
    success: bool

    """
    if title0.lower() == title1.lower() and site0 == site1:
        # copy on it self = no action necessary
        success = True
    else:
        page0 = site0.pages[title0]
        content = page0.text()
        if overwrite:
            success = create_or_overwrite_wiki_page(title1, content, site1)
        else:
            search_result = search_wiki_page(title1, site1)
            if (
                search_result["Result"] and search_result["Exact match"]
            ):  # page already exists
                success = False
            else:
                # search_result["Result"] == True/False
                # search_result["Exact match"] == False
                success = create_or_overwrite_wiki_page(title1, content, site1)
    return success


def copy_list_of_wiki_pages(title_list, site0, site1, overwrite, callback=None):
    """

    Parameters
    ----------
    title_list : list
    site0 : mwclient.client.Site
        Source site object from mwclient lib
    site1 : mwclient.client.Site
        Target site object from mwclient lib
    overwrite : bool
        Whether to overwrite existing pages at target site
    callback : NoneType or function
        Function passed over, to perform operation on the titles of the source pages and
        to be passed as title of the
        target pages. See examples below.
        Example functions:
            capitalize = lambda x: x.capitalize()
            def change_namespace(title, namespace):
                if ":" in namespace:
                    namespace = namespace.split(":")[0]
                if ":" in title:
                    splits = title.split(":")
                    old_name = splits[1].capitalize()
                    new_title = namespace + ":" + old_name
                else:
                    new_title = namespace + ":" + title.capitalize()
                return new_title
        Examples of passing a function as parameter:
            callback = capitalize
            callback = lambda x: x.lower()

    Returns
    -------
    results_dict : dict
        Dictionary, containing the results of the copying operations
    """

    success_list = list()
    fail_list = list()
    for title0 in title_list:
        if callback is None:
            title1 = title0
        else:
            title1 = callback(title0)
        success = copy_wiki_page(title0, title1, site0, site1, overwrite)
        if success:
            success_list.append(title1)
        else:
            fail_list.append(title1)
    results_dict = {
        "Successfully copied pages": success_list,
        "Pages failed to copy": fail_list,
    }
    return results_dict
