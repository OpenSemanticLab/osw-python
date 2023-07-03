from typing import Type

from pydantic import create_model

import osw.model.entity as model


class ControllerTestController(model.Entity):
    def testfunction(self):
        print(f"Entity with label '{str(self.label.text)}'")


def controller_mixin(cls) -> Type:
    # import osw.controller.Entity as controller
    prefix = ""  # "controller."
    postfix = "Controller"
    try:
        eval(f"{prefix}{cls.__name__}{postfix}")
    except NameError:
        # print(f"controller.{cls.__name__} No defined")
        return cls
    else:
        # the controller class
        ctrl_cls = eval(f"{prefix}{cls.__name__}{postfix}")
        # the patched class inheriting both from the data and the controller class
        mixin_cls = create_model(cls.__name__, __base__=tuple([ctrl_cls, cls]))
        return mixin_cls


class ControllerTest(model.Entity):
    pass


ControllerTest = controller_mixin(ControllerTest)


class ControllerTestSubclass(ControllerTest):
    pass


ControllerTestSubclass = controller_mixin(ControllerTestSubclass)

test = ControllerTestSubclass(label=model.Label(text="MyTest"))
test.testfunction()  # while this works, theres no support from static type checking
