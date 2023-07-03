import random
from importlib import reload
from pathlib import Path

import mwclient
import svgwrite
from PIL import Image

import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtSite

DEPENDENCIES = {
    "Entity": "Category:Entity",
    "Item": "Category:Item",
    "WikiFile": "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",
}


def random_image(
    file_path: Path, width: int = 640, height: int = 480, file_type: str = None
) -> None:
    if file_type is None:
        file_type = file_path.suffix[1:].upper()
    if file_type not in ["PNG", "SVG"]:
        raise ValueError(f"Unsupported image format: {file_type}")

    if file_type == "PNG":
        # Define the image dimensions
        width = 640
        height = 480

        # Create a new image with random pixel values
        image = Image.new("RGB", (width, height))
        pixels = image.load()

        for y in range(height):
            for x in range(width):
                # Generate random RGB values for each pixel
                red = random.randint(0, 255)
                green = random.randint(0, 255)
                blue = random.randint(0, 255)

                # Set the pixel color
                pixels[x, y] = (red, green, blue)

        # Save the image
        with open(file_path, "wb") as file:
            image.save(file)
        # image.save(fp=file_path)
    elif file_type == "SVG":
        dwg = svgwrite.Drawing(str(file_path), profile="full", size=(width, height))

        # Generate random shapes or elements
        for _ in range(10):  # Generate 10 random shapes
            shape_type = random.choice(["circle", "rect"])

            if shape_type == "circle":
                cx = random.randint(0, width)
                cy = random.randint(0, height)
                r = random.randint(10, 50)
                dwg.add(dwg.circle(center=(cx, cy), r=r))
            elif shape_type == "rect":
                x = random.randint(0, width)
                y = random.randint(0, height)
                w = random.randint(10, 100)
                h = random.randint(10, 100)
                dwg.add(dwg.rect(insert=(x, y), size=(w, h)))

        dwg.save()


def fetch_dependencies(wtsite_obj: WtSite):
    osw = OSW(site=wtsite_obj)
    categories_fpt = DEPENDENCIES.values()
    for i, cat in enumerate(categories_fpt):
        mode = "append"
        # if i == 0:
        #     mode = "replace"
        osw.fetch_schema(OSW.FetchSchemaParam(schema_title=cat, mode=mode))


def check_dependencies():
    dependencies_met = True
    for key in DEPENDENCIES.keys():
        if not hasattr(model, key):
            dependencies_met = False
            break
    return dependencies_met


def main(wiki_domain: str = None, wiki_username: str = None, wiki_password: str = None):
    dependencies_met = check_dependencies()
    if not dependencies_met:
        # For local testing without tox
        if wiki_domain is None:
            # Make sure that the password file is available
            cwd = Path(__file__).parent.absolute()
            pw_fp = cwd.parents[1] / "examples" / "accounts.pwd.yaml"
            wtsite = WtSite.from_domain(
                domain="wiki-dev.open-semantic-lab.org",
                password_file=str(pw_fp),
            )
        # For testing with tox
        else:
            site = mwclient.Site(host=wiki_domain)
            site.login(username=wiki_username, password=wiki_password)
            # wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
            wtsite = WtSite(site=site)
        fetch_dependencies(wtsite_obj=wtsite)


if __name__ == "__main__":
    main()
    reload(model)
