import os
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from drawio_xml_tools import drawio_xml_tools
import xml.etree.ElementTree as ET
import zlib
import base64

from urllib.parse import unquote
import time


from io import StringIO
from html.parser import HTMLParser

## for pushing to wiki 
import uuid
import wiki_tools as wt
import mwclient



class MLStripper(HTMLParser):   ### from https://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.text = StringIO()
    def handle_data(self, d):
        self.text.write(d)
    def get_data(self):
        return self.text.getvalue()
    
def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def get_uuid():
    return(str(uuid.uuid4()).replace('-',''))


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


class drawio_nx:
    def __init__(self,filename):
        
        self.filename = filename
        self.base_nodes=[]
        self.node_label_map = {"Geräte / Tools":"UsesTool",
            "Geräte":"UsesTool",
            "Tools":"UsesTool",
            "Gegenstand":"HasTarget",
            "Kosten":"HasCost", #### nicht importieren
            "Akteure":"HasActionees",
            "Ergebnisformat":"HasResultFormat",
            "Messgrößen":"HasMeasuredQantities",
            ## Modellierungs-Prozesse
            "Geräte / Tools":"UsesTool",
            "Modell":"UsesModel",
            "Zielgrößen":"HasTargetQuantity",
            ## Daten Prozesse
            "Kategorie":"IsA",
            "Vorgänger":"HasPredecessor",
            "Input-Format":"HasInputFormat",
            "Input":"HasInput",
            "Output":"HasOutput",
            "Output-Format":"HasOutputFormat",
            "Nachfolger":"HasSuccessor",
            "Inline-Messgrößen":"HasInlineMeasurementQuantity"}
        ### todo for later: first check if File is encodedd
        try:
            ## decompress Data to xml
            tree0 = ET.parse(filename)
            data0 = base64.b64decode(tree0.find('diagram').text)
            xml0 = zlib.decompress(data0, wbits=-15)
            xml0 = unquote(xml0)
            
           # print(self.tree)
            self.root = ET.fromstring(xml0)
        except:
            self.tree = ET.parse(filename)
            self.root = self.tree.getroot()
            
            
        self.element_dict={}
        self.DG = nx.DiGraph()

        ###  loop through all elements and store in dict by id
        
        for child in self.root.iter():
            if 'id' in child.attrib.keys():
                #print(f"Child, Tag:{child.tag}, attrib:{child.attrib}\n\n")
                self.element_dict[child.attrib['id']] = child.attrib
                #print(f"id:{child.attrib['id']}   attributes:{child.attrib}\n")
            if 'value' in child.attrib.keys():
                
                #if child.attrib['value'] not in self.node_label_map:
               
                node = child.attrib['id']
                label= self.read_callback(child.attrib['value'])
                self.DG.add_node(child.attrib['id'],label=label)
                
            
        def get_source_and_target_from_child(child):
            
            source_id = None
            target_id = None
        
            if "source" in child.attrib.keys():
                source_id = child.attrib['source']
                
            if "target" in child.attrib.keys():
                target_id = child.attrib['target']
            return(source_id,target_id)
        
        ## get source-target connections between items
        for child in self.root.iter():
            source_id,target_id=get_source_and_target_from_child(child)
            if source_id in self.DG.nodes() and target_id in self.DG.nodes():
                self.DG.add_edge(source_id,target_id,label="IsRelatedTo")
                    
            ## get parenthood relations (only for center node that is an ellipse)
        for child in self.root.iter():
            if 'parent' in child.attrib.keys() and 'id' in child.attrib.keys() and 'style' in child.attrib.keys():# and 'fillColor' in child.attrib.keys() :
                
                if child.attrib['style'].startswith('ellipse'):
                    
                    style_list = child.attrib['style'].split(';')
                    for style in style_list:
                        if style.startswith("fillColor"):
                            color = style.split('=')[1]
                            
                            if not color == "#f5f5f5":
                                
                                parent_id = child.attrib['parent']
                                ## add edge to graph
                                if parent_id in self.DG.nodes() and child.attrib['id'] in self.DG.nodes():
                                    self.base_nodes.append(child.attrib['id'])
                                    
                                    #print("base node is", self.DG.nodes()[self.base_nodes[-1]]['label']," with id ", self.base_nodes[-1])
                                    self.DG.add_edge(child.attrib['id'],parent_id,label="IsA")
                                    #print(f"parent is {self.DG.nodes[parent_id]['label']}")
                                    
                                else:
                                    print(f"parent with id {parent_id} is missing")
               
        self.delete_nodes_by_label(['',"Messgerät X","Messsoftware Y","Material X",
                                    "Komponente Y","Zelle Z","Zeit pro Stück","€ pro g, etc.",
                                    "Eigenschaft X","Eigenschaft Y","Person Z","Abteilung Y",
                                    "Abteilung W","Institut X","Parameter 1","Parameter 2",
                                    "Material X'","Komponente Y'","Zelle Z'","Person Z"])
        self.delete_nodes_by_label(['KurzanleitungBox kann komplett kopiert'],
                                    by_occurrance=True)
        
        
        self.push_node_labels_to_edge_labels()
        
    def push_node_labels_to_edge_labels(self):
        ### replace nodes in 
        
        remove_list = []
        for node in self.DG.nodes():
            if self.DG.nodes[node]["label"] in self.node_label_map.keys():
               
               # print(f"node {self.DG.nodes()[node]['label']}  in: {self.DG.in_edges(node)}, out: {self.DG.out_edges(node)}")
               
                base_node_neighbors=[]
                no_base_node_neighbors=[]
                for neighbor in nx.neighbors(nx.Graph(self.DG),node):
                  #  print(f"neighbor: {self.DG.nodes()[neighbor]['label']}")
                    if neighbor in self.base_nodes: 
                        base_node_neighbors.append(neighbor)
                    else:
                        no_base_node_neighbors.append(neighbor)
                if len(base_node_neighbors)==0:
                    raise ValueError("no base node found, cannot reconnect")
                if len(base_node_neighbors)>1:
                    raise ValueError("base node ambiguous")
                    
                    
                for neighbor in no_base_node_neighbors:
                    #print(base_node_neighbors[0],neighbor)
                    self.DG.add_edge(base_node_neighbors[0],neighbor,label=self.node_label_map[self.DG.nodes()[node]["label"]])
                remove_list.append(node)
        for node in remove_list:
            self.DG.remove_node(node)
                    #print(self.DG.edges()[base_node_neighbors[0]][neighbor])
                    
      
    def read_callback(self,string):
        
        ret = strip_tags(string)
        return(ret)
    
    def delete_nodes_by_label(self,delete_node_list,by_occurrance=False):
        """delets all nodes in self.DG which occurr in delete_node_list"""
        marked_node_list=[]
        for delete_node in delete_node_list:
            for node in self.DG.nodes():
                if by_occurrance:
                    if delete_node in self.DG.nodes[node]['label']:
                        print(f"node with label {self.DG.nodes[node]['label']} will be deleted")
                        marked_node_list.append(node)
                else:
                    if delete_node == self.DG.nodes[node]['label']:
                        marked_node_list.append(node)
        for marked_node in marked_node_list:
            if marked_node in self.DG.nodes():
                self.DG.remove_node(marked_node)
                
                
    def add_edge_from_all_to_new_node(self,new_node_label,connection_label,**kwargs):
        #print(self.filename)
        
        ## find new id :
        new_node = get_uuid()
        self.DG.add_node(new_node,label=new_node_label,**kwargs)
        
        for node in self.DG.nodes():
            if not node == new_node:
                self.DG.add_edge(node,new_node,label=connection_label)
            
    def draw_graph_to_file(self,filename,draw_ege_labels=True,title = None):
        
        fig = plt.figure(figsize=(10,10))
        pos = nx.spring_layout(dxt.DG,k=0.05,iterations = 10)
        #pos = nx.nx_pydot.graphviz_layout(dxt.DG)
        
        node_labels = nx.get_node_attributes(self.DG,"label")
        edge_labels = nx.get_edge_attributes(self.DG,"label")
        
        nx.draw(dxt.DG,with_labels=True,labels=node_labels,pos=pos,node_color="yellow",edge_color="cyan")
        nx.draw_networkx_edge_labels(dxt.DG,pos=pos,edge_labels=edge_labels)
        if title is not None: 
            ax = plt.gca()
            ax.set_title(title)
        fig.savefig(filename)
        
        
    def delete_branches_from_list(self,delete_list=["HasCost"]):
        delete_node_list = []
        for source,target,data in self.DG.edges(data=True):
            
            if "label" in data.keys():
                #print(data['label'],delete_list,data['label'] in delete_list)
                if data['label'] in delete_list:
                    #print("aölskdfjöalkdsjföalksdjföalkdfjaölkdsfjaöldskfjaödslkfjöasdf")
                    delete_node = target
                    successors = [successor for successor in self.DG.successors(delete_node)]
                    for successor in successors:
                        delete_node_list.append(successor)
                    delete_node_list.append(delete_node)
        for delete_node in delete_node_list:
            if delete_node in self.DG.nodes():
                self.DG.remove_node(delete_node)
                
    
def create_DrawIO_page_and_content(site,OSL_name,filepath):
    filename = filepath.split("/")[-1].split("\\")[-1]
    content_string = """"Gerne können Sie Ihr DrawIO Dokument hier einfügen und weiter editiern:\n"""
    content_string +="{{"+f"Template:ELN/Editor/DrawIO|file_name={filename}|page_name={OSL_name}|full_width=0"+"}}\n"
    return(content_string)

def upload_file_to_OSL(site,filepath,OSL_name):
    site.upload(open(filepath, 'rb'), filename=OSL_name, comment="upload by bot")

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
        if "drawIO_path" in DG.nodes[node].keys():
            content+=create_DrawIO_page_and_content(site,OSL_name_dict[node],DG.nodes[node]["drawIO_path"])+"\n"
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
        
def append_institute_to_process_labels(mDG):
    
    for node in mDG.nodes():
        ### if node is linked to a process via IsA
        out_labels=[data['label'] for u,v,data in mDG.out_edges(node,data=True)]
        #print(mDG.nodes[node]['label'],out_labels)
        if "IsA" in out_labels:
            #print(node,mDG.nodes[node])
            target_list = get_nodes_via_edge_label(mDG,node,"IsA")
            CreatedFrom_list = get_nodes_via_edge_label(mDG,node,"CreatedFrom")
            #if target_list is not None:
                #for target in target_list:
                    #print(mDG.nodes[target])
            if CreatedFrom_list is not None:
                for CreatedFrom in CreatedFrom_list:
                    #print(mDG.nodes[CreatedFrom]["label"])
                    Institute = mDG.nodes[CreatedFrom]["label"].split("-")[0].split("_")[0]
                    new_label=f'{mDG.nodes[node]["label"]} ({Institute})'
                    print(new_label)
                    mDG.nodes[node]['label']=new_label
if __name__ == "__main__":
    
    basepath = "Prozesse_Nachtrag"
    get_graphs_from_DrawIO = True
    
    if get_graphs_from_DrawIO:
       
        savepath = "graph_plots"        
        mDG = nx.DiGraph()
        
        for root, dirs, files in os.walk(basepath, topdown=False):
            for name in files:
                if name.endswith('.drawio') or name.endswith(".xml"):
                    if True:# "ISC_Beschichtg_Aktivmaterial.drawio" in name:
                        print('name: ',name)
                        dxt = drawio_nx(os.path.join(root, name))
                        dxt.delete_branches_from_list(delete_list=["HasCost"])
                        dxt.add_edge_from_all_to_new_node(name,"CreatedFrom",drawIO_path=os.path.join(root, name))
                        print(root,name.split('.')[0])
                        dxt.draw_graph_to_file(savepath+"/"+basepath+"/"+name.split('.')[0]+".png")
                        ### add to merged Graph
                        
                        mDG = nx.disjoint_union(mDG,dxt.DG)
                        
    add_node_by_label(mDG,"Prozesse")
    mDG=merge_nodes_with_label_in_list(mDG,["Physische Prozesse","Analytische Methoden","Daten Prozesse","Prozesse","Modellierungs- / Simulations-Methoden"])
    
    ### institutsnamen anpasen (bevor weitere IsA Beziehungen hinzugefügt werden!):
    append_institute_to_process_labels(mDG)
    
    add_edge_by_labels(mDG,"Physische Prozesse","Prozesse",label="IsA")
    add_edge_by_labels(mDG,"Analytische Methoden","Prozesse",label="IsA")
    add_edge_by_labels(mDG,"Modellierungs- / Simulations-Methoden","Prozesse",label="IsA")
    add_edge_by_labels(mDG,"Daten Prozesse","Prozesse",label="IsA")
    
    
        
    ### add Files to Hausaufgaben
    Hausaufgaben_node = add_node_by_label(mDG,"Batterie Digital Hausaufgaben")
    
    add_edge_list=[]
    for node in mDG.nodes():
        label=mDG.nodes[node]['label']
        if label.endswith('.xml') or label.endswith('.drawio'):
            add_edge_list.append(label)
    for node_label in add_edge_list:
        add_edge_by_labels(mDG,node_label,"Batterie Digital Hausaufgaben",label="CreatedBecause")
    
    ### Draw total graph
    if True:
        fig = plt.figure(figsize=(20,20))
        pos = nx.spring_layout(mDG,k=0.05,iterations = 10)
        #pos = nx.nx_pydot.graphviz_layout(dxt.DG)
        node_labels = nx.get_node_attributes(mDG,"label")
        nx.draw(mDG,with_labels=True,labels=node_labels,pos=pos,node_color="yellow",edge_color="cyan")
        edge_labels = nx.get_edge_attributes(mDG,"label")
        nx.draw_networkx_edge_labels(mDG,pos=pos,edge_labels=edge_labels)
        ax = plt.gca()
        ax.set_title("combined Graph")
        fig.savefig(savepath+"/total_graph.png",dpi=300)
        
    ### upload
    if True:
        site = mwclient.Site('batterie-digital.fraunhofer.de', path='/w/')
        user = input("Enter bot username (username@botname)")
        password = input("Enter bot password")
        site.login(user,password)
        
        #delete_by_property_value(site, 1000)
        upload_nx_to_OSL(mDG,site,namespace="Term",upload_id="4")
        
        
    
    