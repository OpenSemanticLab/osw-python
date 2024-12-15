# flake8: noqa: E501
import json

from osw.utils.oold import escape_json_strings
from osw.utils.templates import eval_handlebars_template


def test_category_template():
    template = """
{
    "@context": [
        {{#each subclass_of}}
        "/wiki/{{{.}}}?action=raw\u0026slot=jsonschema"{{#unless @last}},{{/unless}}
        {{/each}}
    ],
    "allOf": [
        {
            {{#each subclass_of}}
            "$ref": "/wiki/{{{.}}}?action=raw\u0026slot=jsonschema"{{#unless @last}},{{/unless}}
            {{/each}}
        }
    ],
    "type": "object",
    "uuid": "{{{uuid}}}",
    "title": "{{{name}}}",
    "title*": {
        {{#each label}}
        "{{{lang}}}": "{{{text}}}"{{#unless @last}},{{/unless}}
        {{/each}}
    },
    "description": "{{{description.[0].text}}}",
    "description*": {
        {{#each description}}
        "{{{lang}}}": "{{{text}}}"{{#unless @last}},{{/unless}}
        {{/each}}
    },
    "required": ["type"],
    "properties": {
        "type": {
            "default": ["{{{_page_title}}}"]
        }
    }
}"""

    data = {
        "type": ["Category:Category"],
        "subclass_of": ["Category:Category"],
        "uuid": "379d5a15-89c7-4c82-bc0d-e47938264d00",
        "label": [{"text": "OwlThing", "lang": "en"}],
        "metaclass": ["Category:OSW725a3cf5458f4daea86615fcbd0029f8"],
        "description": [
            {
                "text": 'Represents the set of all "individuals". In the DL literature this is often called the top concept.',
                "lang": "en",
            }
        ],
        "name": "OwlThing",
    }

    expected = """
{
  "@context": [
    "/wiki/Category:Category?action=raw&slot=jsonschema"
  ],
  "allOf": [
    {
      "$ref": "/wiki/Category:Category?action=raw&slot=jsonschema"
    }
  ],
  "type": "object",
  "uuid": "379d5a15-89c7-4c82-bc0d-e47938264d00",
  "title": "OwlThing",
  "title*": {
    "en": "OwlThing"
  },
  "description": "Represents the set of all \\"individuals\\". In the DL literature this is often called the top concept.",
  "description*": {
    "en": "Represents the set of all \\"individuals\\". In the DL literature this is often called the top concept."
  },
  "required": [
    "type"
  ],
  "properties": {
    "type": {
      "default": [
        "Category:OSW379d5a1589c74c82bc0de47938264d00"
      ]
    }
  }
}
"""

    output = json.loads(
        eval_handlebars_template(
            template,
            escape_json_strings(data),
            {"_page_title": "Category:OSW379d5a1589c74c82bc0de47938264d00"},
        )
    )

    assert output == json.loads(expected)


def test_metamodel_template():
    template = """
    {
        "title": "{{{name}}}",
        "required": ["uuid"],
        "properties": {
            "uuid": {
                "type": "string",
                "format": "uuid",
                "options": {
                    "hidden": true
                }
            } {{#each parameters}},
            "{{{name}}}": {
                "title": "{{{name}}}",
                "type": "{{{type}}}" {{#if default}},
                "default": "{{{default}}}"{{/if}}
            } {{/each}}{{#each submodels}},
            "{{{name}}}":
                {{> self}}
            {{/each}}
        }
    }"""

    data = {
        "submodels": [
            {
                "name": "Geometrie",
                "parameters": [{"name": "FaceArea"}, {"name": "dimension"}],
                "submodels": [
                    {
                        "name": "NegativeElectrode",
                        "parameters": [],
                        "submodels": [
                            {
                                "name": "ActiveMaterial",
                                "parameters": [{"name": "thickness"}],
                                "submodels": [],
                            }
                        ],
                    },
                    {
                        "name": "PositiveElectrode",
                        "parameters": [],
                        "submodels": [
                            {
                                "name": "ActiveMaterial",
                                "parameters": [{"name": "thickness"}],
                                "submodels": [],
                            }
                        ],
                    },
                ],
            }
        ],
        "type": ["Category:OSWecff4345b4b049218f8d6628dc2f2f21"],
        "uuid": "dab254dd-1006-4ddf-9554-64b7a5baf332",
        "name": "BattmoModel",
        "label": [{"text": "BattMo Model", "lang": "en"}],
    }

    expected = """{
        "title":"BattmoModel",
        "required":[
            "uuid"
        ],
        "properties":{
            "uuid":{
                "type":"string",
                "format":"uuid",
                "options":{
                    "hidden":true
                }
            },
            "Geometrie":{
                "title":"Geometrie",
                "required":[
                    "uuid"
                ],
                "properties":{
                    "uuid":{
                    "type":"string",
                    "format":"uuid",
                    "options":{
                        "hidden":true
                    }
                    },
                    "FaceArea":{
                    "title":"FaceArea",
                    "type":""
                    },
                    "dimension":{
                    "title":"dimension",
                    "type":""
                    },
                    "NegativeElectrode":{
                    "title":"NegativeElectrode",
                    "required":[
                        "uuid"
                    ],
                    "properties":{
                        "uuid":{
                            "type":"string",
                            "format":"uuid",
                            "options":{
                                "hidden":true
                            }
                        },
                        "ActiveMaterial":{
                            "title":"ActiveMaterial",
                            "required":[
                                "uuid"
                            ],
                            "properties":{
                                "uuid":{
                                "type":"string",
                                "format":"uuid",
                                "options":{
                                    "hidden":true
                                }
                                },
                                "thickness":{
                                "title":"thickness",
                                "type":""
                                }
                            }
                        }
                    }
                    },
                    "PositiveElectrode":{
                    "title":"PositiveElectrode",
                    "required":[
                        "uuid"
                    ],
                    "properties":{
                        "uuid":{
                            "type":"string",
                            "format":"uuid",
                            "options":{
                                "hidden":true
                            }
                        },
                        "ActiveMaterial":{
                            "title":"ActiveMaterial",
                            "required":[
                                "uuid"
                            ],
                            "properties":{
                                "uuid":{
                                "type":"string",
                                "format":"uuid",
                                "options":{
                                    "hidden":true
                                }
                                },
                                "thickness":{
                                "title":"thickness",
                                "type":""
                                }
                            }
                        }
                    }
                    }
                }
            }
        }
        }"""

    output = json.loads(eval_handlebars_template(template, data))

    assert output == json.loads(expected)


def test_helper_join():
    template = """{
        "@context": [{
        {{#join properties}}
            {{#if rdf_property}}"{{name}}": "{{rdf_property}}"{{/if}}
        {{/join}}
        }]
    }"""

    data = {
        "properties": [
            {
                "name": "test_property",
                "rdf_property": "Property:TestPropertyWithSchema",
            },
            {
                "name": "test_property2",
                "rdf_property": "Property:TestPropertyWithSchema",
            },
        ]
    }

    expected = {
        "@context": [
            {
                "test_property": "Property:TestPropertyWithSchema",
                "test_property2": "Property:TestPropertyWithSchema",
            }
        ]
    }

    output = json.loads(eval_handlebars_template(template, data))

    assert output == expected

    template = """
    {{#join object_array ", " "[" "]"}}{{#if print}}{{value}}{{/if}}{{/join}}
    """

    data = {
        "object_array": [
            {"value": 1, "print": True},
            {"value": 2},
            {"value": 3, "print": True},
        ]
    }

    expected = [1, 3]

    output = json.loads(eval_handlebars_template(template, data))
    assert output == expected


def test_raw_block():
    template = """
{
    "unit": {
        "format": "autocomplete",
        "options": {
            "autocomplete": {
                "query": "[[-HasUnit::{{{quantity}}}]][[HasSymbol::like:*\{{_user_input}}*]]OR[[-HasPrefixUnit.-HasUnit::{{{quantity}}}]][[HasSymbol::like:*\{{_user_input}}*]]|?HasSymbol=label"
            }
        }
    }
}"""

    data = {
        "quantity": "Item:OSW1bd92826da6f5c53982ed6ea45bc1b9b",
    }

    expected = """
{
    "unit": {
        "format": "autocomplete",
        "options": {
            "autocomplete": {
                "query": "[[-HasUnit::Item:OSW1bd92826da6f5c53982ed6ea45bc1b9b]][[HasSymbol::like:*{{_user_input}}*]]OR[[-HasPrefixUnit.-HasUnit::Item:OSW1bd92826da6f5c53982ed6ea45bc1b9b]][[HasSymbol::like:*{{_user_input}}*]]|?HasSymbol=label"
            }
        }
    }
}
"""
    res = eval_handlebars_template(
        template,
        data,
        {"_page_title": "Category:OSW379d5a1589c74c82bc0de47938264d00"},
    )

    output = json.loads(res)

    assert output == json.loads(expected)
