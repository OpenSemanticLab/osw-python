# import all classes from opensemantic.core

from opensemantic.core.v1 import (  # isort:skip
    OswBaseModel,
    Label,
    Entity,
    Item,
    DefinedTerm,
    Keyword,
    IntangibleItem,
    Meta,
    WikiPage,
    LangCode,
    Description,
    ObjectStatement,
    DataStatement,
    QuantityStatement,
    File,
    LocalFile,
    RemoteFile,
    WikiFile,
    PagePackage,
)  # noqa: F401, E402

from opensemantic.base.v1 import (  # isort:skip
    Software,
    PrefectFlow,
)  # noqa: F401, E402
