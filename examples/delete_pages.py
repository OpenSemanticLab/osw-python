from osw.core import WtSite
from osw.express import OswExpress, credentials_fp_default

# (Optional) Set the default credentials filepath to desired location. Otherwise,
# it will use the default location (current working directory)
# credentials_fp_default.set_default(r"C:\Users\gold\ownCloud\Personal\accounts.pwd.yaml")


def delete_pages(
    oswe: OswExpress,
    pages_to_delete: list,
    comment: str = "Delete test pages",
):
    for title in pages_to_delete:
        page = oswe.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
        if page.exists:
            page.delete(comment)
            print("Entity deleted: " + page.get_url())
        else:
            print(f"Entity '{title}' does not exist!")


if __name__ == "__main__":
    # Check setting
    print(f"Credentials loaded from '{str(credentials_fp_default)}")

    # Create an OswExpress object
    domain = "reuse.projects01.open-semantic-lab.org"
    # domain = "arkeve.test.digital.isc.fraunhofer.de"
    oswe_ = OswExpress(domain=domain)

    to_delete = [
        "Item:OSWe2e0ff229fdb4cff9adbf0dc6fd6d9dc",
        "Item:OSW7f6279b69e864f3b99b51424ebcca4e8",
        "Item:OSW9cb17df028214c139ac0add5ed98df44",
        "Item:OSWd1d695e3dab44618bc15361caf4a524a",
        "Item:OSWd59f7c827e114dcf801c3ba98a76756a",
        "Item:OSW5e127f0c49d14d5eb5dd5de4dd5eab13",
        "Item:OSW09cc902953054a779afaf12462a3dd0b",
        "Item:OSW63bd52e27f964cc3b4b66076110c8501",
        "Item:OSW75fc4507c1a44d47be966711de984e59",
        "Item:OSW02f4968583014752aea2d11d13d641fb",
        "Item:OSW59398c6e6eca4163a12a822a89ebbd3a",
        "Item:OSWbb3df035addb48df8ac0334110a1976a",
        "Item:OSW0648497040a74e4888d35529556a65f7",
        "Item:OSW3abf2b154ab4414684defec3685f7a70",
        "Item:OSWb69059f8df7044fcbd55f7e11ec13625",
        "Item:OSW85705394c34d44ddabea2f1a4b06b583",
        "Item:OSW3fe8227fed09446fb8cd5c896b9bfe2d",
        "Item:OSWc2972e28378042c7aedc13d10e9cafb5",
        "Item:OSW5f4777584e364a2a8f02c412e8084082",
        "Item:OSW723ae2356b174fbca28114f24eca85ac",
        "Item:OSW964c691f47ae451592b82c7b0e0fc9ae",
        "Item:OSW1c589c04428c44678c4a2adb4d1103b1",
        "Item:OSWe8290b24db5746b190cc2f5b3f901acf",
        "Item:OSWe8c20f3200b14addba8f5e5d71ff77b0",
        "Item:OSWb4932e68defb442f9086e579f72d178b",
        "Item:OSWb407f9d6c93543878907daea81981e2c",
        "Item:OSW9e5abddf01e14b91b8ea4e4e967e1726",
        "Item:OSW307032e510134526a0607cd8b7100757",
        "Item:OSW533cae76c99349df9fe6dc03ef539f90",
        "Item:OSW99425929e4e54d42a473acb19efd3e53",
        "Item:OSW16802298b939499da404502759c8015d",
        "Item:OSW7cbf9d31dd3640ce81c53b909a36f1fe",
        "Item:OSW5cad87e21943479d87e719d39ac42501",
        "Item:OSW694c58f09d3b4b5caaf0f7107f598ca5",
        "Item:OSWe3e58beab9614f96baed8cb029321c85",
        "Item:OSW7114edb935df497885dbabb2a182f290",
        "Item:OSWd0b2c1ce0cc54539b72f5d49368feea6",
        "Item:OSW876ba11d57f7498299806c0f4c8a7540",
        "Item:OSW2367de1b4d01424ca08400da19a9d63d",
        "Item:OSW4053779f5fbb40f0a5c0c5545d0fa94c",
    ]

    delete_pages(oswe=oswe_, pages_to_delete=to_delete)
