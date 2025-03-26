"""
This example shows how to get the main slot or html content of a OSW page
prerequisite: valid bot password in the used OSW instance (Log in, then 
go to special pages -> Bot passwords ; follow the instructions)
"""
from osw.express import OswExpress
from osw.params import GetPageParam

osw = OswExpress(domain="demo.open-semantic-lab.org")

# the page title of the page to downlaod
# Demo Article
fullpagetitle_to_download = "Item:OSWac34aa10f897463f966724d86eece3da"

## getting the page content from the main slot (without info box...)
page_content = osw.site.get_page(GetPageParam(
    titles = [fullpagetitle_to_download]
)).pages[0].get_slot_content("main")
print(page_content)

## getting the html of the actually visible page including info-box and further elements
page_html = osw.site._site.raw_api(
    action="parse",
    page = fullpagetitle_to_download,
    format="json")
print(page_html)
