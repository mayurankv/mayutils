import cssselect as external_cssselect

from . import etree

SelectorSyntaxError = external_cssselect.SelectorSyntaxError
ExpressionError = external_cssselect.ExpressionError
SelectorError = external_cssselect.SelectorError
__all__ = ["CSSSelector", "ExpressionError", "SelectorError", "SelectorSyntaxError"]

class LxmlTranslator(external_cssselect.GenericTranslator):
    def xpath_contains_function(self, xpath, function): ...

class LxmlHTMLTranslator(LxmlTranslator, external_cssselect.HTMLTranslator): ...

ns = ...

class CSSSelector(etree.XPath):
    def __init__(self, css, namespaces=..., translator=...) -> None: ...
