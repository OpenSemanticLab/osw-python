def get_wikipage_dict(q):
    wt = {'title': get_property_wiki_page_name(q), 'content': [{'OslTemplate:Property/Quantity':{}}]}
    wtq = wt['content'][0]['OslTemplate:Property/Quantity']
    wtq['label'] = qdict[q]['http://www.w3.org/2000/01/rdf-schema#label'][0] 
    if q in qwdict and 'http://www.w3.org/2000/01/rdf-schema#label' in wdict[qwdict[q]]:
        #wtq['label_de'] = getLangLabel(wdict[qwdict[q]]['http://www.w3.org/2000/01/rdf-schema#label'], 'de')
        wtq['label'] = wdict[qwdict[q]]['http://www.w3.org/2000/01/rdf-schema#label']
        for label in wtq['label']: 
            if any(substring in label for substring in ["@zh-cn", "@ms-arab", "@sms", "@smj"]): wtq['label'].remove(label) #unsupported
    else: wtq['label'] = qdict[q]['http://www.w3.org/2000/01/rdf-schema#label'][0] + "@en"         
    wtq['ontology_iri'] = [q]
    if q in qwdict: wtq['ontology_iri'].append(qwdict[q])
    if q in qdbpdict: wtq['ontology_iri'].append(qdbpdict[q])
    wtq['description'] = get_description(q)
    if len(qdict[q]['base_quantity']) == 0:
        wtq['main_unit'] = ""
        wtq['alternative_names'] = []
        wtq['main_unit_ontology_iri'] = []
        wtq['alternative_units'] = []
        units = []
        unit_uris = []
        for cf in qdict[q]['units_by_conversion_factor']:
            wtu = {'alternative_names': [], 'ontology_iri': [], 'use_as_display_unit': 'Yes', 'use_as_input_unit': 'Yes'}
            valid = False
            first = True
            for index, u in enumerate(qdict[q]['units_by_conversion_factor'][cf]):
                #print(u)
                unit_uris.append(u)
                if 'http://qudt.org/schema/qudt/ucumCode' not in udict[u]: 
                    print("Warning: Unit {} without ucum code ignored".format(u))
                    continue
                ucum = udict[u]['http://qudt.org/schema/qudt/ucumCode'][0]
                if '{' in ucum: 
                    print("Warning: Unit {} without invalid char ignored".format(u))
                    continue
                sym = ucum
                if ('[' in sym):
                    print("Warning: Imperial Unit {} only for reference".format(u))
                    wtu['use_as_display_unit'] = 'No'
                    wtu['use_as_input_unit'] = 'No'
                #if ucum in ucum_wu_dict:
                #    if 'http://www.wikidata.org/prop/direct/P5061' in wudict[ucum_wu_dict[ucum]]: 
                #        sym = getLangLabel(wudict[ucum_wu_dict[ucum]]['http://www.wikidata.org/prop/direct/P5061'],'en')
                #    unit_uris.append(ucum_wu_dict[ucum])
                #else: print("Not found: {}".format(ucum))
                units.append(sym)
                if cf == 1.0:
                    if first: 
                        wtq['main_unit'] = sym
                        first = False
                    else: 
                        if len(sym) < len(wtq['main_unit']): #policy: use shortes ucum as main symbol
                            wtq['alternative_names'].append(wtq['main_unit'])
                            wtq['main_unit'] = sym
                        else: wtq['alternative_names'].append(sym)
                    wtq['main_unit_ontology_iri'].append(u)
                if cf != 1.0:
                    wtu['factor'] = str(1.0/cf) #Semantic Mediawiki uses inverse conversion factor
                    if first: 
                        wtu['unit'] = sym
                        first = False
                    else: 
                        if len(sym) < len(wtu['unit']): #policy: use shortes ucum as main symbol
                            wtu['alternative_names'].append(wtu['unit'])
                            wtu['unit'] = sym
                        else: wtu['alternative_names'].append(sym)
                    wtu['ontology_iri'].append(u)
                valid = True
            if cf != 1.0 and valid: wtq['alternative_units'].append({'OslTemplate:Property/Quantity/Unit':wtu})
    else:
        wtq['base_quantity'] = get_property_wiki_page_name(qdict[q]['base_quantity'][0])
        wtq['subquantity_of']=[]
        for sup in qdict[q]['subquantity_of']: wtq['subquantity_of'].append(get_property_wiki_page_name(sup))
        wtq['display_units'] = []
        wtq['input_units'] = []
        for cf in qdict[q]['units_by_conversion_factor']:
            for index, u in enumerate(qdict[q]['units_by_conversion_factor'][cf]):
                if 'http://qudt.org/schema/qudt/ucumCode' not in udict[u]: 
                    print("Warning: Unit {} without ucum code ignored".format(u))
                    continue
                ucum = udict[u]['http://qudt.org/schema/qudt/ucumCode'][0]
                sym = ucum
                if ('[' in sym):
                    print("Warning: Imperial Unit {} ignored".format(u))
                    continue
                wtq['display_units'].append(sym)
                wtq['input_units'].append(sym)
    return wt

def get_wikitext_from_wikipage_dict(d):
    wt = ""
    for key, value in d.items():
        #print("key: {}, valuetype: {}, value: {}".format(key, type(value), "")) 
        if isinstance(value,dict): 
            #print("dict")
            wt += "\n{{" + key
            wt += get_wikitext_from_wikipage_dict(value)
            wt += "\n}}"
        elif isinstance(value,list): 
            #print("list")
            wt += "\n|{}=".format(key)
            for index, element in enumerate(value):
                if isinstance(element,dict): 
                    wt += get_wikitext_from_wikipage_dict(element)
                    #wt += "\n{{" + element
                    #wt += get_wikitext_from_dict(element)
                    #wt += "\n}}"  
                else:
                    if index > 0: wt += ";"
                    wt += element
        else: 
            #print("literal")
            wt += "\n|{}={}".format(key, value)
    return wt

def set_wikitext_from_content(p):
    wt = ""
    for content_element in p['content']:
        if isinstance(content_element,dict): 
            wt += get_wikitext_from_wikipage_dict(content_element)
        elif isinstance(content_element,str): wt += "\n" + content_element
        else: print("Error: content element is not dict or string: {}".format(content_element))
    p['wikitext'] = wt
    return wt