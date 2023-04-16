import osw.model.entity as model


class Entity(model.Entity):
    def explain(self):
        print(f"Entity with label '{str(self.label[0].text)}'")


# model.Entity = Entity
