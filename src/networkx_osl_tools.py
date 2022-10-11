#import os
import networkx as nx
import mwclient



## for pushing to wiki 
import uuid
import wiki_tools as wt

def get_uuid():
    return(str(uuid.uuid4()).replace('-',''))

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def add_node_by_label(DG,label):
    try: 
        node = max(DG.nodes())+1
    except:
        node=get_uuid()
    DG.add_node(node,label=label)
    return(node)
    
def get_node_list_by_label(DG,label):
    return([x for x,y in DG.nodes(data=True) if y['label']==label])
    

def get_node_by_label(DG,label):
    node_list=get_node_list_by_label(DG,label)
    if len(node_list)==1:
        return(node_list[0])
    else:
        return(None)
    
def get_nodes_via_edge_label(DG,start_node,edge_label,outgoing =True):
    
    if outgoing:
        out_list=[target for source,target,data in DG.out_edges(start_node,data=True) if data["label"] is edge_label]
        return(out_list)
        
            
def add_edge_by_labels(DG,label1,label2,label=None):
    """add edge by label if corresponding source and target node exist"""
    
   # print(label1,label2)
    source_node = get_node_by_label(DG,label1)
    target_node = get_node_by_label(DG,label2)
    if source_node is not None and target_node is not None: 
    
        
        DG.add_edge(source_node,target_node,label=label)
        return(True)
    else:
        print("could not add edge by label ",label1,"=>",label2)
        print(f"source_node:{source_node}, target_node:{target_node}")
        
        
        return(False)
    
    
def get_osl_wiki_page_name(params):
    uuid_str = str(uuid.uuid4()).replace('-','')
    page_name = ""
    if params['namespace']: page_name += params['namespace'] + ":"
    page_name += "OSL" + uuid_str
    return page_name

def merge_nodes_with_label_in_list(DG,label_list):
    for label in label_list:
        print('Merge nodes in list:',label_list)
        if label in [data['label'] for id,data in DG.nodes(data=True)]:
            node_list = get_node_list_by_label(DG,label)
            for i in range(1,len(node_list)):
                DG = nx.contracted_nodes(DG,node_list[0],node_list[i])
            print('Merge nodes:',label,node_list)
    return(DG)



def upload_nx_to_OSL(DG,site,namespace="Term",upload_id="4"):
    ## get Term:OSL..UID... page name:
    OSL_name_dict = {}
    for node in DG.nodes():
        OSL_name_dict[node]=get_osl_wiki_page_name({"namespace":namespace})
    
    ## create page content for every node:
        
    i=0
    for node in DG.nodes():
        i+=1
        print(f"upload {i} out of {len(DG.nodes())}: {DG.nodes[node]['label']}")
        
        label=DG.nodes[node]['label']
        
        content = "{{OslTemplate:KB/Term\n"
        content+=f"|label={label}\n"
        content+="|label_lang_code=de\n"
        content+="|description=\n"
        
        content+="|relations={{OslTemplate:KB/Relation\n"
        ## mark automatic upload 
        content+="|property=HasUploadID\n"
        content+=f"|value={upload_id}\n"
        content+="}}"
        ## append property value pairs from outgoing edges
        for source,target,data in DG.out_edges(node,data=True):
            
            if "label" in data:
                prop=data['label']
            else: 
                prop = "PointsTo"
            content+="{{OslTemplate:KB/Relation\n"
            content+=f"|property={prop}\n"
            
            value_id = OSL_name_dict[target]
            content+=f"|value={value_id}\n"
            content+="}}"
            
        content+="}}\n"
        content+="=Details=\n"
        
        ## upload drawio if available:
        content+="\n"
        content+="{{OslTemplate:KB/Term/Footer\n"
        content+="}}"
        #print(content)
       # time.sleep(0.1)
        
        ## do the actual upload
        
        title = OSL_name_dict[node]
       # input(f"create page with title:{title} and label: {node} .")
        #target_page = site.pages[title]
        #target_page.edit(content,'Created by upload_nx_to_OSL')
        wt.create_or_update_wiki_page_with_template(title, content, site, overwrite_with_empty=False)
        #print(f"page created with title: {title} and label {node}")
        
def delete_by_property_value(site,value,prop = "HasUploadID"):
    
    delete_dict={}
    query = f"""[[{prop}::{value}]]|limit=1000"""
    
    result = site.api('ask', query=query, format='json')
    
    if len(result['query']['results'])==0:
        print('No results')
    else:
        for page in result['query']['results'].values():
            if 'printouts' in page:
                key = page['fulltext']
                label = page['displaytitle']
                print(page.keys())
                delete_dict[key]=label
        print(delete_dict)
    #input("Are you sure you want to delete all pages in the list above?")
    i=0
    for key in delete_dict.keys():
        i+=1
        print(f"delete {i} out of {len(delete_dict.keys())}")
        wt.delete_wiki_page(key,site,"BotDelete")
        
def create_test_DG(visualize=False):
    DG = nx.DiGraph()
    DG.add_node(1,label="TestNode1")
    DG.add_node(2,label="TestNode2")
    DG.add_node(3,label="TestNode3")
    
    DG.add_edge(1,2,label="PointsTo")
    DG.add_edge(2,3,label="PointsTo")
    DG.add_edge(1,3,label="PointsTo")
    
    if visualize: 
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(10,10))
        pos = nx.spring_layout(DG,k=0.05,iterations = 10)
        #pos = nx.nx_pydot.graphviz_layout(dxt.DG)
        node_labels = nx.get_node_attributes(DG,"label")
        nx.draw(DG,with_labels=True,labels=node_labels,pos=pos,node_color="yellow",edge_color="cyan")
        edge_labels = nx.get_edge_attributes(DG,"label")
        nx.draw_networkx_edge_labels(DG,pos=pos,edge_labels=edge_labels)
        ax = plt.gca()
        ax.set_title("test_DG")
        fig.show()
    
    return(DG)
        
if __name__=="__main__":
    
    TestDG = create_test_DG(visualize = True)
    
    site_url = input("Enter wiki URL")
    
    site = mwclient.Site(site_url, path='/w/')
    user = input("Enter bot username (username@botname)")
    password = input("Enter bot password")
    site.login(user,password)
    
    upload_id = get_uuid()
    input(f"Press Enter to upload test network with upload_ID {upload_id} ")
    upload_nx_to_OSL(TestDG,site,namespace="Term",upload_id=upload_id)
    
    input("Press Enter to delete test network")
    delete_by_property_value(site, upload_id)