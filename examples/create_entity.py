from pprint import pprint

import osw.model.Entity as model

my_entity = model.Item(
    label=model.Label(text="MyItem"), statements=[model.Statement(predicate="IsA")]
)
pprint(my_entity.dict())
print(my_entity.json())
