from osw.utils.regex_pattern import REGEX_PATTERN_LIB

test_string = """
    {{Template:Viewer/Media
    | image_size = 300
    | mode = default
    | textdata = File:OSW420279d1be9640ad96e6685277a3f29b.png{{!}}Navigation menu;
    File:OSW0024d7c0a0d64642bf51f5facfe85d42{{!}}Search bar;
    File:OSW841b61b5996340fa81c3163bcea87482.png{{!}}Three points menu;
    File:OSWe8c6b659eab14cca927835ccd6baef15.png{{!}}Wiki preferences;
    File:OSWc0df6b35cc964307bbf3d18c78e5cb3e.png{{!}}Alerts;
    File:OSWd173625534d04fe6aab90a7bee4008e2.png{{!}}Notices;
    File:OSWc34ced55461949a59f950283e905b5fc.drawio.png{{!}}Personal menu;
    }}
    """

second_test_string = r"""
{
  "type": [
    "Category:OSW92cc6b1a2e6b4bb7bad470dfdcfdaf26"
  ],
  "author": [],
  "uuid": "d00e7453-f1f3-4a6e-94e6-3c2664fb7776",
  "label": [
    {
      "text": "Full knowledge graph",
      "lang": "en"
    }
  ],
  "description": [
    {
      "text": "Large graph displaying the full knowledge base",
      "lang": "en"
    }
  ],
  "name": "FullKnowledgeGraph",
  "image": "File:OSWc34ced55461949a59f950283e905b5fc.drawio.png"
}
"""

my_dict = {
    "type": ["Category:OSW92cc6b1a2e6b4bb7bad470dfdcfdaf26"],
    "author": [],
    "uuid": "d00e7453-f1f3-4a6e-94e6-3c2664fb7776",
    "label": [{"text": "Full knowledge graph", "lang": "en"}],
    "description": [
        {"text": "Large graph displaying the full knowledge base", "lang": "en"}
    ],
    "name": "FullKnowledgeGraph",
    "image": "File:OSWc34ced55461949a59f950283e905b5fc.drawio.png",
}

my_dict_as_str = str(my_dict)


# Test the regex pattern
# Run the following code in the Python console / this script in interactive console
my_pattern = REGEX_PATTERN_LIB["File page strings from any text"]

search_result = my_pattern.search(test_string)

findall_result = my_pattern.findall(test_string)

full_page_names = my_pattern.findall_by_group_key(test_string, "Full page name")
full_page_names_2 = my_pattern.findall_by_group_key(
    second_test_string, "Full page name"
)
