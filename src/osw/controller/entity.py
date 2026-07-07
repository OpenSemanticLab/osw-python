import osw.model.entity as model


class Entity(model.Entity):
    def explain(self):
        print(f"Entity with label '{self.label[0].text!s}'")


# model.Entity = Entity
