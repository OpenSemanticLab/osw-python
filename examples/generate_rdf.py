import os
from uuid import UUID, uuid5

import osw.model.entity as model
from osw.core import OSW
from osw.express import OswExpress
from osw.utils.wiki import get_full_title
from osw.wtsite import WtSite

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

# load dependencies
DEPENDENCIES = {
    "Tool": "Category:OSWe427aafafbac4262955b9f690a83405d",
}
osw_obj.install_dependencies(DEPENDENCIES, mode="append", policy="if-missing")

# generate a UUID namespace
EXAMPLE_UUID_NAMESPACE = UUID("bd65611d-8669-4903-8a14-af88203acc38")

sensor1 = model.Device(
    uuid=uuid5(EXAMPLE_UUID_NAMESPACE, "Sensor1"),
    name="Sensor1",
    label=[model.Label(text="Sensor 1")],
    description=[model.Description(text="A sensor")],
)

sensor2 = model.Device(
    uuid=uuid5(EXAMPLE_UUID_NAMESPACE, "Sensor2"),
    name="Sensor2",
    label=[model.Label(text="Sensor 2")],
    description=[model.Description(text="Another sensor")],
)

example_machine = model.Device(
    uuid=uuid5(EXAMPLE_UUID_NAMESPACE, "ExampleMachine"),
    name="ExampleMachine",
    label=[model.Label(text="Example Machine")],
    # note: components are modelled as statements to define
    # the relationship between the machine and the components
    components=[
        model.Component(
            # note: uuid format needs to be fixed in schema
            uuid=str(uuid5(EXAMPLE_UUID_NAMESPACE, "sensor_at_position_1")),
            component_id="sensor_at_position_1",
            label=[model.Label(text="Sensor at position 1")],
            component_instance=get_full_title(sensor1),
        ),
        model.Component(
            uuid=str(uuid5(EXAMPLE_UUID_NAMESPACE, "sensor_at_position_2")),
            component_id="sensor_at_position_2",
            label=[model.Label(text="Sensor at position 2")],
            component_instance=get_full_title(sensor2),
        ),
    ],
)

result = osw_obj.export_jsonld(
    params=OSW.ExportJsonLdParams(
        entities=[example_machine, sensor1, sensor2],
        mode=OSW.JsonLdMode.expand,
        build_rdf_graph=True,
        context_loader_config=WtSite.JsonLdContextLoaderParams(
            prefer_external_vocal=False
        ),
    )
)
graph = result.graph
# print all triples in the graph
qres = graph.query(
    """
    SELECT ?s ?p ?o
    WHERE {
    ?s ?p ?o .
    }
    """
)

print("\nAll triples in the graph:")
for row in qres:
    print(row.s, row.p, row.o)

# query all components of example_machine
qres = graph.query(
    """
    SELECT ?component ?clabel
    WHERE {
    ?s Property:HasStatement ?statement .
    ?statement Property:HasProperty Property:HasPart .
    ?statement Property:HasObject ?component .
    ?component Property:HasLabel ?clabel .
    }
    """
)
print("\nComponents of example_machine:")
for row in qres:
    print(row.clabel)

print("\n\nDefine a custom context:")

result = osw_obj.export_jsonld(
    params=OSW.ExportJsonLdParams(
        entities=[example_machine, sensor1, sensor2],
        mode=OSW.JsonLdMode.expand,
        build_rdf_graph=True,
        context={
            "ex": "http://example.org/",
            "components": "@nest",
            "component_instance": {"@id": "ex:hasPart", "@type": "@id"},
            "name": {"@id": "ex:name"},
        },
    )
)
graph = result.graph
# print all triples in the graph
qres = graph.query(
    """
    SELECT ?s ?p ?o
    WHERE {
    ?s ?p ?o .
    }
    """
)
print("\nAll triples in the graph:")
for row in qres:
    print(row.s, row.p, row.o)

# query all components of example_machine
qres = graph.query(
    """
    SELECT ?clabel
    WHERE {
    ?s <http://example.org/hasPart> ?component .
    ?component <http://example.org/name> ?clabel
    }
    """
)
print("\nComponents of example_machine:")
for row in qres:
    print(row.clabel)


print(
    "\n\ncreate a custom class with an additional property mapped in a context extension"
)


class MyCustomDeviceClass(model.Device):
    my_property: str


my_custom_device = example_machine.cast(MyCustomDeviceClass, my_property="test")

result = osw_obj.export_jsonld(
    params=OSW.ExportJsonLdParams(
        entities=[my_custom_device, sensor1, sensor2],
        mode=OSW.JsonLdMode.expand,
        build_rdf_graph=True,
        context_loader_config=WtSite.JsonLdContextLoaderParams(
            prefer_external_vocal=False
        ),
        additional_context={"my_property": "http://example.org/my_property"},
    )
)

graph = result.graph
# print all triples in the graph
qres = graph.query(
    """
    SELECT ?s ?p ?o
    WHERE {
    ?s ?p ?o .
    }
    """
)
print("\nAll triples in the graph:")
for row in qres:
    print(row.s, row.p, row.o)
