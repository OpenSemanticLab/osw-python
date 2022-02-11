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

#merges <template_name> and embedded <subtemplate_name>. text1 is dominant
def mergeWikiText(text1, text2, template_name, subtemplate_param="", subtemplate_name=""):
    if (text1 == text2): return text1
    if (text1 == ""): return text2
    if (text2 == ""): return text1
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
    #print("T1: " + str(t1))
    #print("T2: " + str(t2))
    for p in t2.params:
        if (not t1.has(p.name)):
            t1.add(p.name, p.value)
    if (subtemplate_param != ""): 
        t1.remove(subtemplate_param) 
        for rel2 in r2:
            exists = False
            for rel1 in r1:
                allParamsEqual = True
                for p in rel2.params:
                    if (rel1.has(p.name)):
                        if (not rel1.get(p.name).value.matches(rel2.get(p.name).value)): allParamsEqual = False
                        #print("Compare {}:{} with :{} -> res={}".format(p.name, rel1.get(p.name).value,rel2.get(p.name).value, 
                        #                                                rel1.get(p.name).value.matches(rel2.get(p.name).value)))
                    else: allParamsEqual = False
                if (allParamsEqual): exists = True
            if not exists: r1.append(rel2)
        r1string = ""
        for rel1 in r1:
            r1string += "\r\n   " + str(rel1)
        t1.add(subtemplate_param, r1string)
    #print("Tmerged: " + str(t1))
    non_empty_lines = "\n".join([ll.rstrip() for ll in str(t1).splitlines() if ll.strip()])
    return non_empty_lines

def update_template_within_wikitext(text, template_text, delete=False, remove_empty_lines=False):
    """updates the template parameters in an exisiting wiki <text> with a provided new <template_text>

    Keyword arguments:
    text -- the existing text
    template_text -- the template text with new data
    delete -- if true, params not defined in <template_text> get removed from <text>
    remove_empty_lines -- if true, function will cleanup empty lines within the template code created by the nderlying mwparserfromhell lib (wanted),
    but also within the wiki text around it (unwanted) 
    """
    if (template_text == text): return template_text
    if (template_text == ""): return text
    if (text == ""): return template_text
    new_code = mwparserfromhell.parse(template_text)
    new_template = new_code.filter_templates()[0]
    existing_code = mwparserfromhell.parse(text)
    for template in existing_code.filter_templates(recursive=True):
        if template.name.matches(new_template.name): 
            existing_template = template
            break
    for p in new_template.params:
        if (existing_template.has(p.name)):
            existing_template.get(p.name).value = p.value
        else: existing_template.add(p.name, p.value)
    if (delete):
        for p in existing_template.params:
            if (not new_template.has(p.name)):
                existing_template.remove(p)
    #print("Tmerged: \n" + str(existing_template))
    #print("Text merged: " + str(existing_code))
    new_text = str(existing_code);
    #this will cleanup emptry lines within the template code (wanted), but also within the wiki text around it (unwanted) 
    if (remove_empty_lines): new_text = "\n".join([ll.rstrip() for ll in str(new_text).splitlines() if ll.strip()])
    return new_text
