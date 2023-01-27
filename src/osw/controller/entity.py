import osw.model.entity as model


class Entity(model.Entity):
    def explain(self):
        print(f"Entity with label '{str(self.label.text)}'")


# model.Entity = Entity


class Hardware(model.Hardware, Entity):
    def run(self):
        self.explain()
        print(" is running")


# model.Hardware = Hardware


class DbController(model.Database):
    def create_table(self):
        connection_str = self.db_server
        return connection_str
