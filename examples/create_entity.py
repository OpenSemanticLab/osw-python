from pprint import pprint

import osw.model.entity as model

my_entity = model.Item(
    label=[model.Label(text="MyItem")],
    statements=[model.DataStatement(property="IsA", value="Category:Item")],
)
pprint(my_entity.dict())
print(my_entity.json())
