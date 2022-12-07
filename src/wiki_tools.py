import yaml
import mwclient
import getpass
import mwparserfromhell
import numpy as np
import copy
from jsonpath_ng.ext import parse

def create_site_object(domain, password_file=""):
    """

    Parameters
    ----------
    domain : str
    password_file : str (path to file with <username>\n<password>)

    Returns
    -------
    site : mwclient.client.Site
        Site object from mwclient lib
    """
    domain_dict = {
        "wiki-dev": {"Address": "wiki-dev.open-semantic-lab.org"}
    }
    if domain in domain_dict.keys():
        domain = domain_dict[domain]["Address"]

    site = mwclient.Site(domain, path='/w/')

    if password_file != "":
        with open(password_file, "r") as stream:
            try:
                accounts = yaml.safe_load(stream)
                for domain in accounts:
                    if domain == domain:
                        user = accounts[domain]['username']
                        password = accounts[domain]['password']
            except yaml.YAMLError as exc:
                print(exc)
    else:
        user = input("Enter bot username (username@botname)")
        password = getpass.getpass("Enter bot password")

    site.login(user, password)
    del user
    del password
    return site


# Standard Query
# api.php?action=query&list=prefixsearch&pssearch=Star Wars
def prefix_search(site, text):
    """

    Parameters
    ----------
    site : mwclient.client.Site
        Site object from mwclient lib
    text : str

    Returns
    -------
    page_list : list
    """
    page_list = []
    result = site.api('query', list="prefixsearch", pssearch=text, pslimit=1000, format='json')
    if len(result['query']['prefixsearch']) == 0:
        print('No results')
    else:
        for page in result['query']['prefixsearch']:
            title = page['title']
            print(title)
            page_list.append(title)
    return page_list


# Semantic Query
def semantic_search(site, query):
    """

    Parameters
    ----------
    site : mwclient.client.Site
        Site object from mwclient lib
    query

    Returns
    -------
    page_list : list
    """
    page_list = []
    query += "|limit=1000"
    result = site.api('ask', query=query, format='json')
    if len(result['query']['results']) == 0:
        print("Query '{}' returned no results".format(query))
    else:
        print("Query '{}' returned {} results".format(query, len(result['query']['results'])))
        for page in result['query']['results'].values():
            # why do we do the following?
            if 'printouts' in page:
                title = page['fulltext']
                if '#' not in title:
                    print(title)
                    # original position of "page_list.append(title)" line
            page_list.append(title)
    return page_list


# Page search wrapper
def search_wiki_page(title, site):
    """Adds exact match functionality with ignore-case on top of the prefix_search()'s functionality

    Parameters
    ----------
    title : str
        Title of the wiki page, e. g. User:Someone1234
    site : mwclient.client.Site
        Site object from mwclient lib

    Returns
    -------
    result_dict : dict
    """
    result = site.api('query', list="prefixsearch", pssearch=title, pslimit=1000, format='json')
    if len(result['query']['prefixsearch']) == 0:
        return {"Result": False, "List": list()}
    else:
        exact_match = False
        page_title_list = list()
        for page in result['query']['prefixsearch']:
            page_title = page['title']
            page_title_list.append(page_title)
            if page_title.lower() == title.lower():
                exact_match = True
        result_dict = {"Result": True, "List": page_title_list, "Exact match": exact_match}
        return result_dict
    
def search_redirection_sources(site, target_title, debug = False):
    """Returns a list of pages redirecting to the page with target_title per #REDIRECT [[target]] syntax

    Parameters
    ----------
    site : mwclient.client.Site
        Site object from mwclient lib
    target_title : str
        Title of the target wiki page

    Returns
    -------
    page_list : list of pages redirecting to the page with target_title
    """
    page_list = []
    result = site.api('query', titles=target_title, prop='redirects', format='json')
    if len(result['query']['pages'])==0:
        if (debug): print('No results')
    else:
        for page in result['query']['pages']:
            if not 'redirects' in result['query']['pages'][page]: 
                if (debug): print('No results')
            else:
                for redirecting_source in result['query']['pages'][page]['redirects']:
                    title = redirecting_source['title']
                    page_list.append(title)
    return page_list

def update_template_within_wikitext(text, template_text, delete=False, remove_empty_lines=False, 
                                    overwrite_with_empty=False):
    """Updates the template parameters in an existing wiki <text> with a provided new <template_text>

    Parameters
    ----------
    text : str
        The existing text
    template_text : str
        The template text with new data
    delete : bool
        If true, params not defined in <template_text> get removed from <text>
    remove_empty_lines : bool
        If true, function will cleanup empty lines within the template code created by the underlying mwparserfromhell
        lib (wanted), but also within the wiki text around it (unwanted)
    overwrite_with_empty : bool
        If true, parameters in the existing tempalte will be overwritten even if the parameter value in the 
        template_text is empty

    Returns
    -------
    new_text : str
    """
    if template_text == text: return template_text
    if template_text == "": return text
    if text == "": return template_text
    new_code = mwparserfromhell.parse(template_text)
    new_template = new_code.filter_templates()[0]
    existing_code = mwparserfromhell.parse(text)
    template_names_matched = False 
    for template in existing_code.filter_templates(recursive=True):
        if template.name.matches(new_template.name):
            existing_template = template
            template_names_matched = True
            break
    if template_names_matched:
        for p in new_template.params:
            if existing_template.has(p.name):
                if p.value != "" or overwrite_with_empty:
                    existing_template.get(p.name).value = p.value
            else:
                existing_template.add(p.name, p.value)
        if delete:
            for p in existing_template.params:
                if not new_template.has(p.name):
                    existing_template.remove(p)
    else:  # the original text did not contain a matching template
        # options: 1) include the new template
        # 2) replace the existing template - but what if multiple tempaltes exist on that page?
        pass
    # print("Tmerged: \n" + str(existing_template))
    # print("Text merged: " + str(existing_code))
    new_text = str(existing_code)
    # this will cleanup empty lines within the template code (wanted), but also within the wiki text around it (unwanted)
    if remove_empty_lines: new_text = "\n".join([ll.rstrip() for ll in str(new_text).splitlines() if ll.strip()])
    return new_text


def merge_wiki_page_text(text1, text2, template_name, subtemplate_param="", subtemplate_name=""):
    """Not fully tested function!

    Parameters
    ----------
    text1
    text2
    template_name
    subtemplate_param
    subtemplate_name

    Returns
    -------
    non_empty_lines : str
    """

    if text1 == text2: return text1
    if text1 == "": return text2
    if text2 == "": return text1
    code1 = mwparserfromhell.parse(text1)
    code2 = mwparserfromhell.parse(text2)
    r1 = []
    r2 = []
    for template in code1.filter_templates(recursive=True):
        if template.name.matches(template_name): t1 = template
        if template.name.matches(subtemplate_name): r1.append(template)
    for template in code2.filter_templates(recursive=True):
        if template.name.matches(template_name): t2 = template
        if template.name.matches(subtemplate_name): r2.append(template)
    # print("T1: " + str(t1))
    # print("T2: " + str(t2))
    for p in t2.params:
        if not t1.has(p.name):
            t1.add(p.name, p.value)
    if subtemplate_param != "":
        t1.remove(subtemplate_param)
        for rel2 in r2:
            exists = False
            for rel1 in r1:
                all_params_equal = True
                for p in rel2.params:
                    if rel1.has(p.name):
                        if not rel1.get(p.name).value.matches(rel2.get(p.name).value): all_params_equal = False
                        # print("Compare {}:{} with :{} -> res={}".format(p.name, rel1.get(p.name).value,rel2.get(p.name).value,
                        #                                                rel1.get(p.name).value.matches(rel2.get(p.name).value)))
                    else:
                        all_params_equal = False
                if all_params_equal: exists = True
            if not exists: r1.append(rel2)
        r1string = ""
        for rel1 in r1:
            r1string += "\r\n   " + str(rel1)
        t1.add(subtemplate_param, r1string)
    # print("Tmerged: " + str(t1))
    non_empty_lines = "\n".join([ll.rstrip() for ll in str(t1).splitlines() if ll.strip()])
    return non_empty_lines


def edit_wiki_page_with_content_merge(title, new_content, site, template_name):
    """Edits an existing wiki page, while merging the passed new content with the content of the existing page

    Parameters
    ----------
    title : str
        Title of the wiki page, e. g. User:Someone1234
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
        new_content = merge_wiki_page_text(new_content, source_page_content, template_name=template_name)
        target_page = site.pages[title]
        target_page.edit(new_content, '[bot] update of page content')
        success = True
    else:
        success = False
    return success

def create_flat_content_structure_from_wikitext(text: str, array_mode: str = 'force'):
    """Create a flat python dict (aka 'flat_content_structure' = 'wikiJson') representing the content of the page

    Parameters
    ----------
    text : str
        the wiki source text
    array_mode : str
        defines how to parse template params
        array_mode / param     value   value;  value;value     comment
        'force':               array   array   array           always create an array
        'only_multiple':       literal literal array           create only when more than one value is given
        'delimiter_present':   literal array   array           create array if at least one separator char is present

    Returns
    -------
    res : dict
        (aka 'flat_content_structure' = 'wikiJson')
    """

    res = []
    text = text.strip()
    existing_code = mwparserfromhell.parse(text)
    t_count = 0
    for i in range(0, len(existing_code.nodes)):
        n = existing_code.nodes.pop(0) #returns first layer of nodes. filter() returns also template args
        if (type(n) is mwparserfromhell.nodes.template.Template):
            t_count += 1
            wt = {}
            #print(f"Template: {t.name} = {t}")
            wt[str(n.name).strip()] = {}
            for p in n.params:
                #print(f"  Param: {p.name} = {p.value} ({type(p.value)})")
                wt[str(n.name).strip()][str(p.name)] = create_flat_content_structure_from_wikitext(str(p.value), array_mode)
            res.append(wt)
        else:
            if len(res) == 0 or type(res[-1]) is dict:
                res.append("")
            res[-1] = res[-1] + str(n) #append to previos string if exists
    #for i, x in enumerate(res):
    #    if type(x) is str: res[i] = x.strip() #remove whitespace 
    res = [x for x in res if x and not (type(x) is str and x.isspace())]
    if t_count == 0: 
        res = text
        values = str(text).strip().split(';')
        if array_mode == 'force': res = values
        elif array_mode == 'only_multiple' and len(values) > 1: res = values
        elif array_mode == 'separator_present' and ';' in text: res = values
    return res

def get_wikitext_from_flat_content_dict(d: dict):
    """Create wiki source text from a flat python dict representing a wiki template

    Parameters
    ----------
    d : dict
        flat python dict
        e.g.: {"HeaderTemplate": {"param": "value"}}

    Returns
    -------
    wt : str
        wiki text
    """
    wt = ""
    for key, value in d.items():
        #print("key: {}, valuetype: {}, value: {}".format(key, type(value), "")) 
        if isinstance(value,dict): 
            #print("dict")
            wt += "{{" + key
            wt += get_wikitext_from_flat_content_dict(value)
            wt += "\n}}"
        elif isinstance(value,list): 
            #print("list")
            wt += "\n|{}=".format(key)
            string_index = 0
            for index, element in enumerate(value):
                if isinstance(element,dict): 
                    wt += get_wikitext_from_flat_content_dict(element)
                    #wt += "\n{{" + element
                    #wt += get_wikitext_from_dict(element)
                    #wt += "\n}}"  
                else:
                    if (string_index != index): print(f"Warning: template param '{key}' has mixed template/string values: {value}")
                    if string_index > 0 and element and not element.strip().isspace(): wt += ";"
                    wt += element
                    string_index +=1
        else: 
            #print("literal")
            wt += "\n|{}={}".format(key, value)
    return wt

def get_wikitext_from_flat_content_structure(content):
    """Create wiki source text from the content list (aka 'flat_content_structure' = 'wikiJson') of the page

    Parameters
    ----------
    content : list
        content list, mixed objects (templates) and free text (aka 'flat_content_structure' = 'wikiJson')
        e.g.: [{"HeaderTemplate": {"param": "value"}}, "freetext", {"FooterTemplate": {"param2": "value"}}]

    Returns
    -------
    wt : wiki text
    """
    wt = ""
    for content_element in content:
        if isinstance(content_element,dict): 
            wt += get_wikitext_from_flat_content_dict(content_element)
        elif isinstance(content_element,str): wt += content_element#"\n" + content_element
        else: print("Error: content element is not dict or string: {}".format(content_element))
    return wt

def wikiJson2SchemaJson(schema, wikiJson):
    """Create osl schema-compatible json from the content representation of a page (aka 'flat_content_structure' = 'wikiJson') 

    Parameters
    ----------
    wikiJson : list
        content list, mixed objects (templates) and free text (aka 'flat_content_structure' = 'wikiJson') 
        e.g.: [{"HeaderTemplate": {"param": "value"}}, "freetext", {"FooterTemplate": {"param2": "value"}}]

    Returns
    -------
    schemaJson : dict
        schema-compatible json
        e.g.: {osl_template: "HeaderTemplate", "param": "value", "osl_wikitext": "freetext", "osl_footer": {"osl_template": "FooterTemplate", "param2": "value2"}}
    """
    schemaJson = {}
    if not isinstance(wikiJson[0], dict) or not isinstance(wikiJson[1],str) or not isinstance(wikiJson[2], dict):
        print("Error: Invalid wikiJson:", wikiJson)
        return schemaJson

    schemaJson = wikiJson2SchemaJsonRecursion(schema, wikiJson[0], wikiJson[2])
    schemaJson["osl_wikitext"] = wikiJson[1]
    return schemaJson

def wikiJson2SchemaJsonRecursion(schema: dict, wikiJson: dict, footerWikiJson = None):
    """internal recursion function of wikiJson2SchemaJson()

    Parameters
    ----------
    wikiJson : list
        wiki template representation 
        e.g.: {"HeaderTemplate": {"param": "value"}}

    footerWikiJson : list
        wiki footer template representation 
        e.g.: {"FooterTemplate": {"param2": "value2"}}

    Returns
    -------
    schemaJson : dict
        schema-compatible json
        e.g.: {osl_template: "HeaderTemplate", "param": "value", "osl_footer": {"osl_template": "FooterTemplate", "param2": "value2"}}
    """
    schemaJson = {}
    if footerWikiJson != None:
        schemaJson['osl_footer'] = wikiJson2SchemaJsonRecursion(schema, footerWikiJson)
        
    for key in wikiJson:
        value = wikiJson[key]
        if isinstance(value,list): 
            schemaJson[key] = []
            for index, element in enumerate(value):
                element = value[index]
                if isinstance(element,dict): 
                    if key == "extensions":
                        if footerWikiJson != None: #we asume that every extension provides also a footer template
                            nextFooter = footerWikiJson[schemaJson['osl_footer']['osl_template']]['extensions'][index]
                            schemaJson[key].append(wikiJson2SchemaJsonRecursion(schema, element, nextFooter))
                    else: schemaJson[key].append(wikiJson2SchemaJsonRecursion(schema, element))
                else:
                    schemaJson[key].append(element)
                    
        elif isinstance(value,dict): 
            schemaJson = wikiJson2SchemaJsonRecursion(schema, value, footerWikiJson)
            schemaJson['osl_template'] = key
        else:
            schemaJson[key] = value


    if 'osl_template' in schemaJson:
        jsonpath_expr = parse('$..properties')#[?osl_template.default = "' + schemaJson['osl_template'] + '"]')
        schema_def = {}
        #print("Search for ", schemaJson['osl_template'])
        for match in jsonpath_expr.find(schema):
            value = match.value
            if value['osl_template']['default'] == schemaJson['osl_template']:
                schema_def = match.value #ToDo: Resolve allOf...
                #print(schema_def)

        for key in list(schemaJson.keys()):
            if key in schema_def:
                if 'type' in schema_def[key]: #use schema to resolve types
                    if schema_def[key]['type'] == 'integer': schemaJson[key] = int(schemaJson[key])
                    elif schema_def[key]['type'] == 'float': schemaJson[key] = float(schemaJson[key])
                    elif schema_def[key]['type'] == 'number': schemaJson[key] = float(schemaJson[key])
                    elif schema_def[key]['type'] == 'string': schemaJson[key] = str(schemaJson[key])
                    elif schema_def[key]['type'] == 'array':
                        if not isinstance(schemaJson[key], list): del schemaJson[key]
                        elif len(schemaJson[key]) == 0: del schemaJson[key]
                else: #assume type==object
                    if isinstance(schemaJson[key], list) and len(schemaJson[key]) == 1: schemaJson[key] = schemaJson[key][0]
            else: #fall back
                if schemaJson[key] == "" and key == 'extensions': del schemaJson[key]
                elif isinstance(schemaJson[key], list): #wikiJson defaults are lists, even for single or empty values
                    if len(schemaJson[key]) == 0: del schemaJson[key]
                    #elif len(schemaJson[key]) == 1: schemaJson[key] = schemaJson[key][0]

    return schemaJson

def schemaJson2WikiJson(schemaJson, isRoot = True):
    """Create content representation of a page (aka 'flat_content_structure' = 'wikiJson')  from the osl schema-compatible json

    Parameters
    ----------
    schemaJson : dict
        schema-compatible json
        e.g.: {osl_template: "HeaderTemplate", "param": "value", "osl_wikitext": "freetext", "osl_footer": {"osl_template": "FooterTemplate", "param2": "value2"}}

    isRoot: boolean
        indicates first call in recursion

    Returns
    -------
    wikiJson : list
        content list, mixed objects (templates) and free text (aka 'flat_content_structure' = 'wikiJson') 
        e.g.: [{"HeaderTemplate": {"param": "value"}}, "freetext", {"FooterTemplate": {"param2": "value"}}]
    """
    wikiJson = [{}, "", {}]; #header, freetext, footer
    template = ""
    footer_template = ""
    if 'osl_template' in schemaJson:
        template = schemaJson['osl_template']
        wikiJson[0][template] = {}
    else:
        print("Error: Mandatory property 'osl_template' not found in schemaJson", schemaJson)
        return

    if 'osl_wikitext' in schemaJson: wikiJson[1] = schemaJson['osl_wikitext']
    if 'osl_footer' in schemaJson:
        wikiJson[2] = schemaJson2WikiJson(schemaJson['osl_footer'], False)[0]
        footer_template = schemaJson['osl_footer']['osl_template']
        wikiJson[2][footer_template]['extensions'] = []
    
    for key in schemaJson:
        if key.startswith('_') or key.startswith('osl_template') or key.startswith('osl_wikitext') or key.startswith('osl_footer'): continue #exclude private and reserved keywords
        if schemaJson[key] == None: continue
        if isinstance(schemaJson[key], list):
            wikiJson[0][template][key] = []
            for subSchemaJson in schemaJson[key]:
                subWikiJson = schemaJson2WikiJson(subSchemaJson, False)
                wikiJson[0][template][key].append(subWikiJson[0])
                if (key == "extensions"):
                    wikiJson[2][footer_template]['extensions'].append(subWikiJson[2])

        elif isinstance(schemaJson[key], dict):
            subWikiJson = schemaJson2WikiJson(schemaJson[key], False)
            wikiJson[0][template][key] = [subWikiJson[0]]
        else:
            wikiJson[0][template][key] = schemaJson[key]

    return wikiJson


def create_or_overwrite_wiki_page(title, content, site):
    """Creates a page with the passed title and content. If the page already exists, the prior content is replaced with
    the passed content.

    Parameters
    ----------
    title : str
        Title of the wiki page, e. g. User:Someone1234
    content : str
    site : mwclient.client.Site
        Site object from mwclient lib

    Returns
    -------
    success : bool
    """
    target_page = site.pages[title]
    target_page.edit(content, '[bot] create page')
    success = True
    return success


def delete_wiki_page(title, site, reason):
    """Deletes the wiki page with the passed title, if it was found (exact match!), otherwise returns False

    Parameters
    ----------
    title : str
        Title of the wiki page, e. g. User:Someone1234
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


def create_or_update_wiki_page_with_template(title, content, site, overwrite_with_empty=False):
    """Creates a wiki page with a template included in the content. If the page does already exist, the parameters
    within the template are update

    Parameters
    ----------
    title : str
        Title of the wiki page, e. g. User:Someone1234
    content : str
    site : mwclient.client.Site
        Site object from mwclient lib
    overwrite_with_empty : bool
        Decided whether a template parameter's value in an preexisting page is overwritten with an empty value

    Returns
    -------
    success : bool
    """
    search_result = search_wiki_page(title, site)
    if search_result["Result"]:
        existing_page = site.pages[title]
        existing_text = existing_page.text()
        # update the page's content (template only)
        updated_content = update_template_within_wikitext(text=existing_text, template_text=content, overwrite_with_empty=overwrite_with_empty)
        success = create_or_overwrite_wiki_page(title, updated_content, site)
    else:
        # just create the page
        success = create_or_overwrite_wiki_page(title, content, site)
    return success


def find_dependencies(wikitext, debug=False):
    """Finds templates, properties and categories within wikitext

    Parameters
    ----------
    wikitext : str
    debug : bool
        Whether to print debugging messages

    Returns
    -------
    filtered_dependencies : list
    """
    dependencies = []
    code = mwparserfromhell.parse(wikitext)
    for template in code.filter_templates(recursive=True):
        if template.name.split(':')[0].isupper():
            if debug: print("MagicWord: {}".format(template.name))
        elif template.name[0] == "#":
            if debug: print("ParserFunction: {}".format(template.name))
            if "#set:" in template.name or "#declare:" in template.name:
                if '=' in template.name.split(':')[1]:  # in case of '{{#set:HasIdPostfix={{{id_postfix}}} }}'
                    property_ = "Property:" + template.name.split(':')[1].split('=')[0]
                    dependencies.append(property_)
                    if debug: print("=> {}".format(property_))
                for param in template.params:
                    property_ = "Property:" + param.split('=')[0]
                    dependencies.append(property_)
                    if debug: print("=> {}".format(property_))
        else:
            if debug: print("Template: {}".format(template.name))
            template_name = str(template.name)
            if ':' not in template.name:
                template_name = "Template:" + template_name
            dependencies.append(template_name)
            if debug: print("=> {}".format(template_name))
    # for tag in code.filter_tags(recursive=True):
    #    if (debug): print("Tag: {}".format(tag))
    for link in code.filter_wikilinks(recursive=True):
        if '::' in link:
            if debug: print("Annotation: {}".format(link))
            property_ = "Property:" + link.split('::')[0].split('[[')[-1]
            dependencies.append(property_)
            if debug: print("=> {}".format(property_))
        if 'Category:' in link:
            if debug: print("Category: {}".format(link))
            category = link.replace('[[', '').replace(']]', '')
            dependencies.append(str(category))
            if debug: print("=> {}".format(category))
        else:
            if debug: print("Link: {}".format(link))
    dependencies = np.unique(dependencies).tolist()  # remove duplicates
    filtered_dependencies = []  # do not manipulate the iterated object
    for dependency in dependencies:
        # ensure no leading or trailing white spaces 
        dependency = dependency.strip()
        # very frew page titles listed here contain invalid characters "\n"
        dependency = dependency.replace('\n', '')        
        # see https://www.semantic-mediawiki.org/wiki/Help:Special_properties
        if 'Property:' in dependency and (' ' in dependency or '_' in dependency):
            if debug: print("Info: Remove presumptive built-in property {}".format(dependency))
        else:            
            filtered_dependencies.append(dependency)
    return filtered_dependencies


def find_dependencies_recursively(title, site, dependencies=[], debug=False):
    """Finds all included templates, properties and categories within a wiki page

    Parameters
    ----------    
    title : str
        Title of the wiki page, e. g. User:Someone1234
    site : mwclient.client.Site
        Site object from mwclient lib    
    dependencies
        List of already found dependent titles
    debug : bool
        Whether to print debugging messages

    Returns
    -------
    dependencies : list
    """
    title = title.replace("{", "").replace("}", "")
    page = site.pages[title]
    content = page.text()
    new_dependencies = find_dependencies(content, debug)
    for dependency in new_dependencies:
        if dependency not in dependencies:  # for circular dependencies
            dependencies.append(dependency)
            if debug: print("Scan nested {}".format(dependency))
            find_dependencies_recursively(dependency, site, dependencies=dependencies, debug=debug)
    return dependencies


def extend_page_list_with_recursive_dependencies(page_list, site):
    """Finds all included templates, properties and categories for a list of wiki pages and appends them to the list

    Parameters
    ----------    
    page_list : list or iterable
        List of pages
    site : mwclient.client.Site
        Site object from mwclient lib

    Returns
    -------
    page_list : list
    """
    page_list_iter = copy.deepcopy(page_list)
    for page in page_list_iter:
        # we provide the updates page list to prevent a revisit of the pages
        dependencies = find_dependencies_recursively(page, site, dependencies=page_list, debug=False)
        page_list.extend(dependencies)
    page_list = np.unique(page_list)
    return page_list


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
            if search_result["Result"] and search_result["Exact match"]:  # page already exists
                success = False
            else:  # search_result["Result"] == True/False, search_result["Exact match"] == False
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
        Function passed over, to perform operation on the titles of the source pages and to be passed as title of the
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
    results_dict = {"Successfully copied pages": success_list, "Pages failed to copy": fail_list}
    return results_dict
