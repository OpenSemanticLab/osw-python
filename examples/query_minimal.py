from osw.express import OswExpress

# Create an OswExpress object
domain = "wiki-dev.open-semantic-lab.org"
osw = OswExpress(domain=domain)
instances = osw.site.semantic_search(
    "[[Category:OSW44deaa5b806d41a2a88594f562b110e9]]"  # Persons ins OSW
    "[[HasOu::Item:OSWb961cad90656513babc4e928472538c4]]"  # that are member of the OU
)
print(instances)
