import mwclient
import getpass
import mwparserfromhell
import numpy as np

def createSiteObj(domain):
    site = mwclient.Site(domain, path='/w/')
    user = input("Enter bot username (username@botname)")
    password = getpass.getpass("Enter bot password")
    site.login(user, password)
    del user
    del password
    return site

#Standard Query
#api.php?action=query&list=prefixsearch&pssearch=Star Wars
def prefixSearch(site, text):
    page_list = []
    result = site.api('query', list="prefixsearch", pssearch=text, pslimit=1000, format='json')
    if len(result['query']['prefixsearch'])==0:
        print('No results')
    else:
        for page in result['query']['prefixsearch']:
            title = page['title']
            print(title)
            page_list.append(title)
    return page_list

#Semantic Query
def semanticSearch(site, query):
    page_list = []
    query += "|limit=1000"
    result = site.api('ask', query=query, format='json')
    if len(result['query']['results'])==0:
        print('No results')
    else:
        print("{} results".format(len(result['query']['results'])))
        for page in result['query']['results'].values():
            if 'printouts' in page:
                title = page['fulltext']
                if ('#' not in title): 
                    print(title)
                    page_list.append(title)
    return page_list

#finds templates, properties and categories within wikitext
def findDependencies(wikitext, debug=False):
    dependencies = []
    code = mwparserfromhell.parse(wikitext)
    for template in code.filter_templates(recursive=True):
        if template.name.split(':')[0].isupper():
            if (debug): print("MagicWord: {}".format(template.name))
        elif template.name[0] == "#":
            if (debug): print("ParserFunction: {}".format(template.name))    
            if ("#set:" in template.name or "#declare:" in template.name):
                if ('=' in template.name.split(':')[1]): #in case of '{{#set:HasIdPostfix={{{id_postfix}}} }}'
                    property = "Property:" + template.name.split(':')[1].split('=')[0]
                    dependencies.append(property)
                    if (debug): print("=> {}".format(property))
                for param in template.params:
                    property = "Property:" + param.split('=')[0]
                    dependencies.append(property)
                    if (debug): print("=> {}".format(property))

        else:
            if (debug): print("Template: {}".format(template.name))
            template_name = str(template.name)
            if (':' not in template.name):
                template_name = "Template:" + template_name
            dependencies.append(template_name)
            if (debug): print("=> {}".format(template_name))
    #for tag in code.filter_tags(recursive=True):
    #    if (debug): print("Tag: {}".format(tag))
    for link in code.filter_wikilinks(recursive=True):
        if ('::' in link):
            if (debug): print("Annotation: {}".format(link))
            property = "Property:" + link.split('::')[0].split('[[')[-1]
            dependencies.append(property)
            if (debug): print("=> {}".format(property))
        if ('Category:' in link):
            if (debug): print("Category: {}".format(link))
            category = link.replace('[[','').replace(']]','')
            dependencies.append(str(category))
            if (debug): print("=> {}".format(category))
        else:
            if (debug): print("Link: {}".format(link))
    dependencies = np.unique(dependencies).tolist() #remove duplicates
    filtered_dependencies = [] #do not manipulate the iterated object
    for dependency in dependencies:
        #see https://www.semantic-mediawiki.org/wiki/Help:Special_properties
        if 'Property:' in dependency and (' ' in dependency or '_' in dependency):
            print("Info: Remove presumptive built-in property {}".format(dependency))
        else: filtered_dependencies.append(dependency)
    return filtered_dependencies

#finds all included templates, properties and categories within a wiki page
def findDependenciesRecursive(site, title, dependencies=[], debug=False):
    page = site.pages[title]
    content = page.text();
    new_dependencies = findDependencies(content, debug)
    for dependency in new_dependencies:
        if (dependency not in dependencies): #for circular dependencies
            dependencies.append(dependency)
            if (debug): print("Scan nested {}".format(dependency))
            findDependenciesRecursive(site, dependency, dependencies=dependencies, debug=debug)
    return dependencies

#finds all included templates, properties and categories for a list of wiki pages and appends them to the list
def extendPageListWithRecursiveDependencies(page_list):
    for page in page_list:
        #we provide the updates page list to prevent a revisit of the pages
        dependencies = findDependenciesRecursive(site, page, dependencies=page_list, debug=False)
        page_list.extend(dependencies)
    page_list = np.unique(page_list)
    return page_list
