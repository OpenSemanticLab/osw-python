import os
import pandas as pd
from pathlib import Path
import json

def dict_to_json(dictionary, name_of_json, optional_orient=None, optional_path=None):
    if optional_orient is None:
        df_json = pd.DataFrame.from_dict(dictionary)
    else:
        df_json = pd.DataFrame.from_dict(dictionary, orient=optional_orient)
    if optional_path is None: 
        filepath_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"{name_of_json}.json")
        print(filepath_json)
    else: 
        Path(optional_path)    
    # filepath_json.parent.mkdir(parents=True, exist_ok=True)  
    df_json.to_json(filepath_json)  
    
