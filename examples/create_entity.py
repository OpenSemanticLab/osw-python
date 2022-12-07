import sys
import os
from pprint import pprint

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #add parent dir to path

import src.model.KB.Entity as model

my_entity = model.Entity(label=model.Label(label_text="MyEntity"), statements=[model.Statement(predicate="IsA")])
pprint(my_entity.dict())
print(my_entity.json())