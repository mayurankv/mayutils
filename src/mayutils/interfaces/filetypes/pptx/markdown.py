r"""
Convert markdown source text into formatted PowerPoint text frame content.

Translates CommonMark-style markdown into PowerPoint ``TextFrame``
content by walking the parsed token tree and emitting runs and
paragraphs with the appropriate character and paragraph-level
formatting. Handles inline emphasis, hyperlinks, code spans and
blocks, ordered/unordered/task lists with nested levels, blockquotes,
headings scaled relative to the base font size, thematic breaks,
footnotes, highlighting, and super/subscript via a ``baseline``
extension to ``CT_TextCharacterProperties``. Provides the bridge
between the ``mistune``-based parser in
:mod:`mayutils.interfaces.filetypes.markdown` and the ``python-pptx``
shape model consumed by slide-composition helpers elsewhere in this
package.

See Also
--------
mayutils.interfaces.filetypes.markdown : Supplies the ``mistune``
    parser that produces the token tree consumed here.
mayutils.interfaces.filetypes.pptx.units : Length helpers used for
    margins, indents and paragraph spacing.
pptx.util : Source of :class:`pptx.util.Pt` unit conversions used
    throughout this module.

Examples
--------
>>> from pptx import Presentation
>>> from mayutils.interfaces.filetypes.pptx.markdown import (
...     add_markdown_to_text_frame,
... )
>>> presentation = Presentation()
>>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
>>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
>>> _ = add_markdown_to_text_frame(
...     "# Title\\n\\n- item **1**\\n- item *2*",
...     text_frame=shape.text_frame,
...     font_size=18,
... )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes.markdown import EMOJI_MAP, create_markdown_parser
from mayutils.interfaces.filetypes.pptx.units import Length
from mayutils.objects.colours import Colour

with may_require_extras():
    from lxml.etree import SubElement, _Element  # pyright: ignore[reportPrivateUsage]
    from pptx.oxml import register_element_cls
    from pptx.oxml.ns import qn
    from pptx.oxml.simpletypes import ST_Coordinate32
    from pptx.oxml.text import CT_TextCharacterProperties
    from pptx.oxml.xmlchemy import OptionalAttribute
    from pptx.util import Pt

if TYPE_CHECKING:
    from pptx.text.text import TextFrame, _Paragraph, _Run  # pyright: ignore[reportPrivateUsage]


class CT_TextCharacterPropertiesExtended(CT_TextCharacterProperties):  # noqa: N801
    """
    Extend PowerPoint run properties with a ``baseline`` shift attribute.

    Adds an optional ``baseline`` attribute to the ``python-pptx``
    ``CT_TextCharacterProperties`` oxml wrapper so runs can be shifted
    vertically relative to the baseline. Without this extension the
    base class does not surface the ``baseline`` OOXML attribute,
    which is required to express superscript (positive values) and
    subscript (negative values) formatting emitted by
    :func:`set_run_formatting`. The class is swapped in for every
    ``a:rPr`` element parsed by ``python-pptx`` via
    :func:`pptx.oxml.register_element_cls` at import time.

    Attributes
    ----------
    baseline
        Vertical baseline offset measured in 1/100000 of the font
        height, per the OOXML ``ST_Coordinate32`` simple type. Positive
        values raise the text (superscript); negative values lower it
        (subscript).

    See Also
    --------
    set_run_formatting : Consumer of the ``baseline`` attribute when
        rendering ``^sup^`` and ``~sub~`` markdown tokens.
    pptx.oxml.text.CT_TextCharacterProperties : Base class extended
        here to add the ``baseline`` attribute.
    pptx.oxml.simpletypes.ST_Coordinate32 : OOXML simple type that
        defines the valid range of ``baseline`` values.

    Notes
    -----
    The class is registered as the handler for ``a:rPr`` elements at
    module import time via :func:`pptx.oxml.register_element_cls` so
    that every run-properties element parsed by ``python-pptx``
    exposes the ``baseline`` attribute.

    Examples
    --------
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     CT_TextCharacterPropertiesExtended,
    ... )
    >>> CT_TextCharacterPropertiesExtended.__name__
    'CT_TextCharacterPropertiesExtended'
    """

    baseline = OptionalAttribute("baseline", ST_Coordinate32)


register_element_cls(nsptagname="a:rPr", cls=CT_TextCharacterPropertiesExtended)


# Header sizes relative to base font size
HEADER_SIZES = {
    1: 2.0,
    2: 1.5,
    3: 1.25,
    4: 1.1,
    5: 1.0,
    6: 0.9,
}

# Code font family
CODE_FONT = "Consolas"


def get_or_add_first_paragraph(
    text_frame: TextFrame,
    /,
) -> _Paragraph:
    """
    Return the first paragraph of a text frame, creating one if absent.

    Serves as the entry point when emitting markdown content so the
    renderer can reuse an existing (possibly empty) paragraph that
    ``python-pptx`` provisions for every new text frame rather than
    leaving it blank above the generated content. When the frame
    already holds at least one paragraph the existing first paragraph
    is returned verbatim; otherwise a fresh paragraph is appended and
    returned so downstream code can immediately add runs to it.

    Parameters
    ----------
    text_frame
        The PowerPoint text frame whose leading paragraph should be
        retrieved or materialised.

    Returns
    -------
    _Paragraph
        The existing first paragraph of ``text_frame`` when one is
        present, otherwise a newly appended empty paragraph that
        becomes the first paragraph of the frame.

    See Also
    --------
    add_markdown_to_text_frame : Top-level caller that seeds markdown
        rendering against the returned paragraph.
    process_list_item : Uses this helper when emitting the first
        list-item paragraph of a list block.
    pptx.util : Provides the ``python-pptx`` types involved in the
        returned paragraph object.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     get_or_add_first_paragraph,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> paragraph = get_or_add_first_paragraph(shape.text_frame)
    >>> paragraph._p is shape.text_frame.paragraphs[0]._p
    True
    """
    if len(text_frame.paragraphs) == 0:
        return text_frame.add_paragraph()

    return text_frame.paragraphs[0]


def set_run_formatting(  # noqa: C901
    run: _Run,
    /,
    *,
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    strikethrough: bool | None = None,
    font_size: int | None = None,
    font_family: str | None = None,
    font_colour: Colour | None = None,
    highlight_colour: Colour | None = None,
    hyperlink: str | None = None,
    hyperlink_colour: Colour | None = None,
    superscript: bool = False,
    subscript: bool = False,
) -> None:
    """
    Apply character-level formatting attributes to a PowerPoint text run.

    Mutates the font, highlight, hyperlink and baseline sub-elements
    of a ``python-pptx`` run to match inline markdown semantics such
    as emphasis, strong, code spans, marks and links. Each optional
    argument that is left as ``None`` leaves the corresponding run
    attribute untouched, which lets callers both establish fresh
    formatting for new runs and overlay additional attributes onto
    previously styled runs. Highlight, superscript and subscript
    values are emitted directly into the OOXML run-properties element
    using helpers from :mod:`pptx.oxml` because they are not surfaced
    by the high-level ``python-pptx`` font API.

    Parameters
    ----------
    run
        The ``python-pptx`` run whose font, highlight, hyperlink and
        baseline properties will be mutated in place.
    bold
        If set, toggles bold weight on the run's font.
    italic
        If set, toggles italic style on the run's font.
    underline
        If set, toggles underline decoration on the run's font.
    strikethrough
        When truthy, writes ``strike="sngStrike"`` onto the run
        properties element to render a single-line strikethrough.
    font_size
        Desired font size in points, converted to EMUs via
        :func:`pptx.util.Pt`.
    font_family
        Typeface name applied to the run's font (for example
        ``"Calibri"`` or ``"Consolas"``).
    font_colour
        Foreground text colour; its ``pptx_colour`` RGB representation
        is assigned to the font colour.
    highlight_colour
        Background highlight applied by inserting ``a:highlight`` and
        ``a:srgbClr`` sub-elements into the run properties using the
        colour's hex representation.
    hyperlink
        URL to attach to the run. When provided the run is turned into
        a clickable link targeting this address.
    hyperlink_colour
        Override text colour applied only when ``hyperlink`` is also
        given, allowing link text to diverge from default font colour.
    superscript
        If ``True``, raises the run by 30% of its font height by
        writing ``baseline=30000`` on the run properties element.
    subscript
        If ``True``, lowers the run by 25% of its font height by
        writing ``baseline=-25000`` on the run properties element.

    See Also
    --------
    CT_TextCharacterPropertiesExtended : Adds the ``baseline``
        attribute read by the super/subscript branches here.
    process_inline_tokens : Primary caller that dispatches inline
        markdown tokens through this helper.
    pptx.util : Provides :class:`pptx.util.Pt` used to convert sizes.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     set_run_formatting,
    ... )
    >>> from mayutils.objects.colours import Colour
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> paragraph = shape.text_frame.paragraphs[0]
    >>> run = paragraph.add_run()
    >>> run.text = "hello"
    >>> set_run_formatting(
    ...     run,
    ...     bold=True,
    ...     italic=True,
    ...     font_size=14,
    ...     font_colour=Colour.parse("#FF0000"),
    ... )
    """
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if underline is not None:
        run.font.underline = underline
    if strikethrough:
        run.font._rPr.attrib["strike"] = "sngStrike"  # pyright: ignore[reportUnknownMemberType, reportPrivateUsage]  # noqa: SLF001
    if font_size is not None:
        run.font.size = Pt(font_size)
    if font_family is not None:
        run.font.name = font_family
    if font_colour is not None:
        run.font.color.rgb = font_colour.pptx_colour
    if highlight_colour is not None:
        rPr = run.font._rPr  # pyright: ignore[reportPrivateUsage]  # noqa: N806, SLF001
        highlight = SubElement(_parent=rPr, _tag=qn(namespace_prefixed_tag="a:highlight"))
        srgbClr = SubElement(_parent=highlight, _tag=qn(namespace_prefixed_tag="a:srgbClr"))  # noqa: N806
        srgbClr.set(key="val", value=highlight_colour.to_str(method="hex").lstrip("#"))  # pyright: ignore[reportUnknownMemberType]
    if hyperlink is not None:
        run.hyperlink.address = hyperlink
        if hyperlink_colour is not None:
            run.font.color.rgb = hyperlink_colour.pptx_colour
    if superscript:
        run.font._rPr.baseline = 30000  # pyright: ignore[reportAttributeAccessIssue, reportPrivateUsage] # 30% above baseline  # noqa: SLF001
    if subscript:
        run.font._rPr.baseline = -25000  # pyright: ignore[reportAttributeAccessIssue, reportPrivateUsage] # 25% below baseline  # noqa: SLF001


def process_inline_tokens(  # noqa: C901, PLR0912, PLR0915
    paragraph: _Paragraph,
    /,
    *,
    tokens: list[dict[str, Any]],
    formatting_stack: dict[str, Any],
    font_size: int | None = None,
    font_family: str | None = None,
    font_colour: Colour | None = None,
    highlight_colour: Colour | None = None,
    hyperlink_colour: Colour | None = None,
) -> None:
    """
    Walk inline markdown tokens and emit formatted runs onto a paragraph.

    Recurses into container tokens (emphasis, strong, underline,
    strikethrough, mark, super/subscript and link) while accumulating
    style state so that leaf ``text``, ``codespan``, ``softbreak`` and
    ``linebreak`` tokens are rendered with the correct combined
    formatting. The ``formatting_stack`` mapping is copied before each
    recursive call so nested styling does not leak to sibling tokens,
    and inline hyperlink attributes captured from the ``link`` token's
    ``attrs.url`` field are propagated down so deeply nested emphasis
    inside a link still carries the hyperlink target.

    Parameters
    ----------
    paragraph
        Target paragraph to which new runs will be appended.
    tokens
        Sequence of inline tokens produced by the markdown parser.
        Each token is expected to carry a ``type`` key and optionally
        ``raw``, ``children`` and ``attrs`` entries.
    formatting_stack
        Active formatting context inherited from outer tokens.
        Recognised keys include ``bold``, ``italic``, ``underline``,
        ``strikethrough``, ``highlight``, ``hyperlink``, ``code_font``,
        ``superscript`` and ``subscript``. The mapping is copied
        before recursion so mutations do not leak to siblings.
    font_size
        Base font size (in points) applied to emitted runs.
    font_family
        Base typeface for text runs; overridden for ``codespan``
        tokens where :data:`CODE_FONT` is always used.
    font_colour
        Default foreground colour for text runs.
    highlight_colour
        Default highlight colour used when a ``mark`` token does not
        override it.
    hyperlink_colour
        Override colour applied when rendering link text through
        :func:`set_run_formatting`.

    See Also
    --------
    set_run_formatting : Applies each accumulated style to the newly
        created run.
    add_markdown_to_text_frame : Top-level caller that invokes this
        helper for paragraph and heading tokens.
    mayutils.interfaces.filetypes.markdown : Hosts the ``mistune``
        parser producing the inline tokens consumed here.

    Notes
    -----
    Unknown token types are handled gracefully: if they contain
    ``children`` they are descended into with the current formatting
    context; otherwise any ``raw`` text they carry is emitted as a
    plain run.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     process_inline_tokens,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> paragraph = shape.text_frame.paragraphs[0]
    >>> tokens = [
    ...     {"type": "text", "raw": "hello "},
    ...     {
    ...         "type": "strong",
    ...         "children": [{"type": "text", "raw": "world"}],
    ...     },
    ... ]
    >>> process_inline_tokens(
    ...     paragraph,
    ...     tokens=tokens,
    ...     formatting_stack={},
    ...     font_size=12,
    ... )
    """
    for token in tokens:
        token_type = token.get("type")

        if token_type == "text":  # noqa: S105
            run = paragraph.add_run()
            run.text = token.get("raw", "")
            set_run_formatting(
                run,
                bold=formatting_stack.get("bold"),
                italic=formatting_stack.get("italic"),
                underline=formatting_stack.get("underline"),
                strikethrough=formatting_stack.get("strikethrough"),
                font_size=font_size,
                font_family=formatting_stack.get("code_font") or font_family,
                font_colour=font_colour,
                highlight_colour=formatting_stack.get("highlight") or highlight_colour,
                hyperlink=formatting_stack.get("hyperlink"),
                hyperlink_colour=hyperlink_colour,
                superscript=formatting_stack.get("superscript", False),
                subscript=formatting_stack.get("subscript", False),
            )

        elif token_type == "emphasis":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["italic"] = True
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "strong":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["bold"] = True
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "underline":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["underline"] = True
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "strikethrough":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["strikethrough"] = True
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "mark":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["highlight"] = highlight_colour or Colour.parse("#FFFF00")
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "superscript":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["superscript"] = True
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "subscript":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["subscript"] = True
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "codespan":  # noqa: S105
            run = paragraph.add_run()
            run.text = token.get("raw", "")
            set_run_formatting(
                run,
                bold=formatting_stack.get("bold"),
                italic=formatting_stack.get("italic"),
                font_size=font_size,
                font_family=CODE_FONT,
                font_colour=font_colour,
                highlight_colour=Colour.parse("#E8E8E8"),
            )

        elif token_type == "link":  # noqa: S105
            new_stack = formatting_stack.copy()
            new_stack["hyperlink"] = token.get("attrs", {}).get("url", "")
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=new_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "softbreak":  # noqa: S105
            run = paragraph.add_run()
            run.text = " "
            set_run_formatting(
                run,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
            )

        elif token_type == "linebreak":  # noqa: S105
            run = paragraph.add_run()
            run.text = "\n"

        # Handle unknown inline types by processing children if present
        elif "children" in token:
            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack=formatting_stack,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )
        elif "raw" in token:
            run = paragraph.add_run()
            run.text = token.get("raw", "")
            set_run_formatting(
                run,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
            )


def add_bullet_subelement(
    parent: _Element,
    /,
    *,
    tagname: str,
    **kwargs: str,
) -> _Element:
    """
    Create and attach a child OOXML element with the given attributes.

    Builds up the ``a:pPr`` bullet-formatting sub-tree by creating a
    qualified-namespace sub-element underneath ``parent`` and writing
    each keyword argument onto it as an attribute. Centralising this
    pattern keeps :func:`set_paragraph_bullet` concise because every
    bullet component (``a:buChar``, ``a:buFont``, ``a:buAutoNum``,
    ``a:buSzPct``) can be attached with a single call, avoiding
    repetitive ``SubElement``/``set`` calls and keeping the
    ``python-pptx`` internals scoped to this helper.

    Parameters
    ----------
    parent
        OOXML element to which the new sub-element should be appended.
    tagname
        Qualified tag name (for example ``"a:buChar"``) of the child
        element to create; resolved to a fully-qualified name via
        :func:`pptx.oxml.ns.qn`.
    **kwargs
        Attribute name/value pairs written onto the new element.

    Returns
    -------
    etree._Element
        The newly created sub-element, after it has been attached to
        ``parent``.

    See Also
    --------
    set_paragraph_bullet : Main consumer of this helper when assembling
        bullet glyph, bullet font and auto-numbering elements.
    pptx.oxml.ns.qn : Namespace-prefix resolver used to build the
        qualified tag name expected by ``lxml``.
    pptx.util : Upstream module that owns the OOXML types the returned
        element integrates with.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     add_bullet_subelement,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> paragraph = shape.text_frame.paragraphs[0]
    >>> pPr = paragraph._p.get_or_add_pPr()
    >>> element = add_bullet_subelement(
    ...     pPr,
    ...     tagname="a:buChar",
    ...     char="*",
    ... )
    >>> element.get("char")
    '*'
    """
    element = SubElement(_parent=parent, _tag=qn(namespace_prefixed_tag=tagname))

    for key, value in kwargs.items():
        element.set(key, value)

    return element


def set_paragraph_bullet(
    paragraph: _Paragraph,
    /,
    *,
    level: int = 0,
    numbered: bool = False,
    bullet_char: str | None = None,
    space_before: int | None = 10,
    space_after: int | None = 0,
    bullet_size_pct: int = 100000,  # 100% = 100000
    from_placeholder: bool = False,
) -> None:
    """
    Configure bullet glyph or auto-numbering formatting on a paragraph.

    Sets the paragraph indent level and vertical spacing, then either
    leaves bullet rendering to the placeholder (when
    ``from_placeholder`` is true) or writes an explicit bullet
    definition into the paragraph properties. Any pre-existing
    ``a:buNone``, ``a:buChar``, ``a:buFont``, ``a:buAutoNum`` and
    ``a:buSzPct`` children are removed first so repeated calls
    produce idempotent output, and the hanging indent is derived from
    fixed EMU constants so nested levels stay visually aligned with
    the outer list.

    Parameters
    ----------
    paragraph
        The paragraph whose bullet formatting is being configured;
        both its ``level``/spacing properties and its underlying
        ``a:pPr`` element are mutated in place.
    level
        Outline level of the paragraph; controls nesting depth and
        the left margin added on top of ``base_margin``.
    numbered
        When ``True`` emits an ``a:buAutoNum`` element with
        ``type="arabicPeriod"`` producing ``1.`` style numbering;
        otherwise a character bullet is rendered.
    bullet_char
        Custom glyph for the unordered-list bullet. When ``None`` the
        filled bullet ``"•"`` is used. Ignored when ``numbered`` is
        ``True``.
    space_before
        Space (in points) added above the paragraph. ``None`` leaves
        the existing value untouched.
    space_after
        Space (in points) added below the paragraph. ``None`` leaves
        the existing value untouched.
    bullet_size_pct
        Bullet glyph size expressed in thousandths of a percent of
        the text size (``100000`` = 100%).
    from_placeholder
        When ``True``, only the indent level and spacing are applied
        so that the host placeholder's own bullet styling is
        preserved; no explicit bullet XML is emitted.

    See Also
    --------
    add_bullet_subelement : Helper that attaches the bullet,
        auto-number and font sub-elements to the paragraph.
    set_paragraph_task : Equivalent helper for task-list checkbox
        bullets.
    pptx.util : Supplies :class:`pptx.util.Pt` used for spacing.

    Notes
    -----
    The hanging indent is derived from fixed EMU constants
    (``base_margin`` and ``indent_per_level``) yielding roughly
    0.375" per level with a 0.1875" hanging indent.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     set_paragraph_bullet,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> paragraph = shape.text_frame.paragraphs[0]
    >>> paragraph.add_run().text = "nested item"
    >>> set_paragraph_bullet(paragraph, level=1, numbered=False)
    """
    # Set the indentation level using python-pptx's built-in property
    paragraph.level = level

    # Set spacing between bullet points
    if space_before is not None:
        paragraph.space_before = Pt(points=space_before)
    if space_after is not None:
        paragraph.space_after = Pt(points=space_after)

    # If from_placeholder, just set the level and let the placeholder handle bullets
    if from_placeholder:
        return

    # Access the underlying XML to set bullet style
    pPr = paragraph._p.get_or_add_pPr()  # pyright: ignore[reportPrivateUsage]  # noqa: N806, SLF001

    # Remove any existing bullet-related elements
    for tag in ("a:buNone", "a:buChar", "a:buFont", "a:buAutoNum", "a:buSzPct"):
        existing = pPr.find(qn(namespace_prefixed_tag=tag))  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if existing is not None:
            pPr.remove(existing)  # pyright: ignore[reportUnknownMemberType]

    # marL = left margin (positive), indent = hanging indent (negative for bullets).
    base_margin = Length.from_inches(0.375)
    indent_per_level = Length.from_inches(0.375)
    bullet_indent = Length.from_inches(0.1875)

    pPr.set("marL", str(base_margin + (indent_per_level * level)))  # pyright: ignore[reportUnknownMemberType]
    pPr.set("indent", str(-bullet_indent))  # pyright: ignore[reportUnknownMemberType]

    if numbered:
        # Add auto-numbering
        add_bullet_subelement(
            pPr,
            tagname="a:buAutoNum",
            type="arabicPeriod",
        )
    else:
        # Add bullet size percentage
        add_bullet_subelement(
            pPr,
            tagname="a:buSzPct",
            val=str(bullet_size_pct),
        )

        # Add bullet font
        add_bullet_subelement(
            pPr,
            tagname="a:buFont",
            typeface="Arial",
            panose="020B0604020202020204",
            pitchFamily="34",
            charset="0",
        )

        # Add bullet character (default: filled square)
        char = bullet_char if bullet_char is not None else "•"
        add_bullet_subelement(
            pPr,
            tagname="a:buChar",
            char=char,
        )


def set_paragraph_task(
    paragraph: _Paragraph,
    /,
    *,
    checked: bool = False,
    level: int = 0,
    space_before: int | None = 6,
    space_after: int | None = 0,
) -> None:
    """
    Apply a checkbox-style bullet to a paragraph for task-list items.

    Removes any pre-existing bullet character, number or "no bullet"
    directive from the paragraph's ``a:pPr`` element and inserts a
    single ``a:buChar`` whose glyph encodes the checked/unchecked
    state. Task-list markers produced by markdown syntax such as
    ``- [ ]`` and ``- [x]`` are rendered with ballot-box and check-
    mark glyphs so slides visually mirror the source document while
    still participating in PowerPoint's outline indentation model.

    Parameters
    ----------
    paragraph
        Paragraph that will be restyled as a task-list entry.
    checked
        If ``True`` the checked-box glyph from
        :data:`EMOJI_MAP` (key ``"checkmark"``) is used; otherwise the
        empty ballot box ``"☐"`` is written.
    level
        Outline level controlling the indent depth.
    space_before
        Space in points before the paragraph; ``None`` skips writing
        the property.
    space_after
        Space in points after the paragraph; ``None`` skips writing
        the property.

    See Also
    --------
    set_paragraph_bullet : Companion helper for non-task bullet and
        auto-number formatting.
    process_list_item : Detects task-list markers and routes them
        through this helper.
    pptx.util : Supplies :class:`pptx.util.Pt` used for spacing.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     set_paragraph_task,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> paragraph = shape.text_frame.paragraphs[0]
    >>> paragraph.add_run().text = "buy milk"
    >>> set_paragraph_task(paragraph, checked=True, level=0)
    """
    # Set the indentation level
    paragraph.level = level

    # Set spacing between items
    if space_before is not None:
        paragraph.space_before = Pt(points=space_before)
    if space_after is not None:
        paragraph.space_after = Pt(points=space_after)

    pPr = paragraph._p.get_or_add_pPr()  # pyright: ignore[reportPrivateUsage]  # noqa: N806, SLF001

    buNone = pPr.find(qn(namespace_prefixed_tag="a:buNone"))  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # noqa: N806
    if buNone is not None:
        pPr.remove(buNone)  # pyright: ignore[reportUnknownMemberType]

    # Remove any existing auto-numbering
    buAutoNum = pPr.find(qn(namespace_prefixed_tag="a:buAutoNum"))  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # noqa: N806
    if buAutoNum is not None:
        pPr.remove(buAutoNum)  # pyright: ignore[reportUnknownMemberType]

    buChar = pPr.find(qn(namespace_prefixed_tag="a:buChar"))  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # noqa: N806
    if buChar is None:
        buChar = SubElement(_parent=pPr, _tag=qn(namespace_prefixed_tag="a:buChar"))  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]  # noqa: N806
    buChar.set("char", EMOJI_MAP["checkmark"] if checked else "☐")  # pyright: ignore[reportUnknownMemberType]


def process_list_item(
    *,
    text_frame: TextFrame,
    token: dict[str, Any],
    level: int,
    numbered: bool,
    first_paragraph: bool,
    font_size: int | None,
    font_family: str | None,
    font_colour: Colour | None,
    highlight_colour: Colour | None,
    hyperlink_colour: Colour | None,
    bullet_char: str | None,
    from_placeholder: bool,
) -> bool:
    r"""
    Render a single markdown list-item token into the text frame.

    Emits one paragraph per ``paragraph``/``block_text`` child of the
    list item, detects GitHub-flavoured task-list markers to switch
    between checkbox and bullet styling, and recurses into nested
    lists via :func:`process_list`. Inline content is first written
    with :func:`process_inline_tokens` and then the bullet or task
    decoration is applied afterwards because ``python-pptx``
    overwrites the run-level XML when a bullet is attached to an
    empty paragraph, which would otherwise wipe out newly added runs.

    Parameters
    ----------
    text_frame
        Target text frame being populated.
    token
        List-item token whose ``children`` are block-level elements
        (inline paragraphs and possibly nested lists).
    level
        Indent depth of this item within the overall list hierarchy.
    numbered
        ``True`` if the enclosing list is ordered so numbered bullets
        are emitted; ``False`` for unordered bullet lists.
    first_paragraph
        Whether the next paragraph written should reuse the text
        frame's existing first paragraph rather than appending a new
        one.
    font_size
        Base font size in points to apply to rendered runs.
    font_family
        Default typeface for rendered runs.
    font_colour
        Default text colour.
    highlight_colour
        Default highlight colour forwarded to inline rendering.
    hyperlink_colour
        Colour override applied to hyperlink runs.
    bullet_char
        Custom bullet glyph forwarded to :func:`set_paragraph_bullet`.
    from_placeholder
        When ``True`` the paragraph's level is set but the
        placeholder's own bullet styling is retained.

    Returns
    -------
    bool
        Updated value of ``first_paragraph``: ``False`` once any
        paragraph has been emitted so subsequent callers append new
        paragraphs instead of reusing the first.

    See Also
    --------
    process_list : Wrapper that iterates the list-item siblings and
        dispatches each one through this helper.
    set_paragraph_task : Styling helper invoked for task-list items.
    set_paragraph_bullet : Styling helper invoked for ordered and
        unordered list items.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     add_markdown_to_text_frame,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> _ = add_markdown_to_text_frame(
    ...     "- [ ] todo\\n- [x] done",
    ...     text_frame=shape.text_frame,
    ... )
    """
    children: list[dict[str, Any]] = token.get("children", [])

    for child in children:
        child_type = child.get("type")

        if child_type in ("paragraph", "block_text"):
            if first_paragraph:
                paragraph = get_or_add_first_paragraph(text_frame)
                first_paragraph = False
            else:
                paragraph = text_frame.add_paragraph()

            # Check if this is a task list item
            is_task = False
            checked = False
            inline_children = child.get("children", [])
            if inline_children and inline_children[0].get("type") == "task_list_marker":
                is_task = True
                checked = inline_children[0].get("attrs", {}).get("checked", False)
                inline_children = inline_children[1:]

            # First add the text content
            process_inline_tokens(
                paragraph,
                tokens=inline_children,
                formatting_stack={},
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

            # Then set bullet formatting (after text is added)
            if is_task:
                set_paragraph_task(
                    paragraph,
                    checked=checked,
                    level=level,
                )
            else:
                set_paragraph_bullet(
                    paragraph,
                    level=level,
                    numbered=numbered,
                    bullet_char=bullet_char,
                    from_placeholder=from_placeholder,
                )

        elif child_type in ("list", "bullet_list", "ordered_list"):
            first_paragraph = process_list(
                text_frame=text_frame,
                token=child,
                level=level + 1,
                first_paragraph=first_paragraph,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
                bullet_char=bullet_char,
                from_placeholder=from_placeholder,
            )

    return first_paragraph


def process_list(
    *,
    text_frame: TextFrame,
    token: dict[str, Any],
    level: int,
    first_paragraph: bool,
    font_size: int | None,
    font_family: str | None,
    font_colour: Colour | None,
    highlight_colour: Colour | None,
    hyperlink_colour: Colour | None,
    bullet_char: str | None,
    from_placeholder: bool,
) -> bool:
    r"""
    Render a markdown list token and its items onto a text frame.

    Determines whether the list is ordered by inspecting the token's
    ``attrs.ordered`` flag, then delegates each ``list_item`` child to
    :func:`process_list_item`. Because ``mistune`` represents both
    ordered and unordered lists with the same ``list`` token type,
    the ordering flag must be read off the token before dispatch, and
    nested lists are emitted at ``level + 1`` and beyond so
    PowerPoint's outline indentation mirrors the markdown nesting.

    Parameters
    ----------
    text_frame
        Target text frame receiving the rendered list paragraphs.
    token
        Parsed ``list`` (or ``bullet_list``/``ordered_list``) token
        whose ``children`` are individual list-item tokens.
    level
        Starting outline level for items of this list; nested lists
        are emitted at ``level + 1`` and beyond.
    first_paragraph
        Whether the first paragraph of the text frame is still
        available for reuse before any content has been written.
    font_size
        Base font size in points for rendered runs.
    font_family
        Default typeface for rendered runs.
    font_colour
        Default text colour forwarded to inline rendering.
    highlight_colour
        Default highlight colour forwarded to inline rendering.
    hyperlink_colour
        Colour used for hyperlink runs.
    bullet_char
        Custom bullet glyph applied to unordered items.
    from_placeholder
        When ``True``, defers bullet glyph styling to the placeholder
        and only sets indent levels.

    Returns
    -------
    bool
        Updated ``first_paragraph`` flag reflecting whether any
        paragraphs were emitted during processing.

    See Also
    --------
    process_list_item : Renders each child list-item token dispatched
        from this helper.
    add_markdown_to_text_frame : Top-level renderer that triggers list
        processing for every ``list`` block-level token.
    mayutils.interfaces.filetypes.markdown : Hosts the ``mistune``
        parser producing the list tokens consumed here.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     add_markdown_to_text_frame,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> _ = add_markdown_to_text_frame(
    ...     "1. first\\n2. second",
    ...     text_frame=shape.text_frame,
    ... )
    """
    token_type = token.get("type")
    numbered = token_type == "list" and token.get("attrs", {}).get("ordered", False)  # noqa: S105

    for item in token.get("children", []):
        if item.get("type") == "list_item":
            first_paragraph = process_list_item(
                text_frame=text_frame,
                token=item,
                level=level,
                numbered=numbered,
                first_paragraph=first_paragraph,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
                bullet_char=bullet_char,
                from_placeholder=from_placeholder,
            )

    return first_paragraph


def add_markdown_to_text_frame(  # noqa: C901, PLR0912, PLR0915
    markdown: str,
    /,
    *,
    text_frame: TextFrame,
    font_family: str | None = None,
    font_size: int | None = None,
    line_spacing: float | None = None,
    text_alignment: Literal["left", "center", "right", "justify"] | None = None,
    font_colour: Colour | str | None = None,
    highlight_colour: Colour | str | None = None,
    hyperlink_colour: Colour | str | None = None,
    bullet_char: str | None = None,
    from_placeholder: bool = False,
) -> TextFrame:
    r"""
    Render a markdown document into a PowerPoint text frame.

    Parses ``markdown`` with the shared library markdown parser, then
    walks the block-level tokens and emits paragraphs and runs so the
    resulting text frame mirrors the source document's structure and
    inline formatting. Heading sizes are derived from ``font_size``
    via :data:`HEADER_SIZES`, blockquotes are prefixed with a
    box-drawing gutter rendered in grey italic, fenced code blocks
    pick up the monospace :data:`CODE_FONT` and a light background
    highlight, and any ``footnote_list`` tokens are deferred until
    after the main body so they can be rendered below a thin
    separator rule with superscript keys.

    Parameters
    ----------
    markdown
        Source markdown document. The following syntax is honoured:
        ``**bold**``, ``*italic*``, ``__underline__``,
        ``~~strikethrough~~``, inline `` `code` ``, ``- item`` and
        ``1. item`` lists (with indentation for nesting), ``> quote``
        blockquotes, fenced code blocks, ``[text](url)`` hyperlinks,
        ``# Header`` through ``###### Header``, ``:emoji:`` shortcodes,
        ``==highlight==``, ``X^2^`` superscript, ``X~2~`` subscript,
        ``- [ ]``/``- [x]`` task lists and footnotes.
    text_frame
        Target text frame that will be populated; its existing first
        paragraph is reused for the first block-level token produced
        by the parser.
    font_family
        Default typeface for non-code runs (for example ``"Arial"``
        or ``"Calibri"``).
    font_size
        Default font size in points. Header sizes are scaled from
        this value via :data:`HEADER_SIZES`; when ``None`` a base of
        ``24`` points is used for heading scaling.
    line_spacing
        Multiplier assigned to each emitted paragraph's
        ``line_spacing`` (for example ``1.5`` for 150%).
    text_alignment
        Horizontal alignment applied to paragraphs and headings;
        ``None`` leaves the default alignment in place.
    font_colour
        Default text colour. Strings are parsed via
        :meth:`Colour.parse`.
    highlight_colour
        Default highlight colour used by ``==marked==`` inline
        tokens when they do not supply their own colour.
    hyperlink_colour
        Override colour for hyperlink text.
    bullet_char
        Custom glyph for unordered list bullets; defaults to the
        filled bullet character when ``None``.
    from_placeholder
        When ``True`` the function assumes ``text_frame`` belongs to
        a placeholder that already carries bullet formatting and only
        applies paragraph indent levels. In this mode, the input must
        contain only list or blank-line tokens.

    Returns
    -------
    TextFrame
        The same ``text_frame`` instance after all paragraphs and
        runs have been appended, returned for call chaining.

    Raises
    ------
    ValueError
        If ``from_placeholder`` is ``True`` and ``markdown`` contains
        any block-level token other than a list or a blank line.

    See Also
    --------
    mayutils.interfaces.filetypes.markdown : Supplies
        :func:`create_markdown_parser` used to tokenise the input.
    process_inline_tokens : Emits runs for inline tokens inside
        paragraphs, headings and blockquotes.
    process_list : Handles ordered, unordered and task-list blocks.
    pptx.util : Supplies :class:`pptx.util.Pt` used for default
        font-size conversions.

    Notes
    -----
    Footnote definitions collected from ``footnote_list`` tokens are
    appended at the end of the text frame, preceded by a thin
    separator rule rendered from box-drawing characters.

    Examples
    --------
    >>> from pptx import Presentation
    >>> from mayutils.interfaces.filetypes.pptx.markdown import (
    ...     add_markdown_to_text_frame,
    ... )
    >>> presentation = Presentation()
    >>> slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    >>> shape = slide.shapes.add_textbox(0, 0, 5000000, 3000000)
    >>> source = "# Heading\\n\\nSome **bold** text with [a link](https://example.com).\\n"
    >>> populated = add_markdown_to_text_frame(
    ...     source,
    ...     text_frame=shape.text_frame,
    ...     font_family="Calibri",
    ...     font_size=14,
    ... )
    >>> populated._txBody is shape.text_frame._txBody
    True
    """
    # Parse colours if strings
    if font_colour is not None and not isinstance(font_colour, Colour):
        font_colour = Colour.parse(font_colour)
    if highlight_colour is not None and not isinstance(highlight_colour, Colour):
        highlight_colour = Colour.parse(highlight_colour)
    if hyperlink_colour is not None and not isinstance(hyperlink_colour, Colour):
        hyperlink_colour = Colour.parse(hyperlink_colour)

    # Parse markdown to AST
    parser = create_markdown_parser(renderer=None)
    tokens = cast("list[dict[str, Any]]", parser(markdown))

    # Validate that markdown only contains lists when from_placeholder=True
    if from_placeholder:
        allowed_types = {"list", "blank_line"}
        for token in tokens:
            token_type = token.get("type")
            if token_type not in allowed_types:
                msg = f"When from_placeholder=True, markdown must only contain lists. Found: {token_type}"
                raise ValueError(msg)

    # Track whether we've used the first paragraph
    first_paragraph = True
    footnotes_content: dict[str, list[dict[str, Any]]] = {}

    # Process block-level tokens
    for token in tokens:
        token_type = token.get("type")

        if token_type == "paragraph":  # noqa: S105
            if first_paragraph:
                paragraph = get_or_add_first_paragraph(text_frame)
                first_paragraph = False
            else:
                paragraph = text_frame.add_paragraph()

            if line_spacing is not None:
                paragraph.line_spacing = line_spacing
            if text_alignment is not None:
                from pptx.enum.text import PP_ALIGN  # noqa: PLC0415

                alignment_map = {
                    "left": PP_ALIGN.LEFT,
                    "center": PP_ALIGN.CENTER,
                    "right": PP_ALIGN.RIGHT,
                    "justify": PP_ALIGN.JUSTIFY,
                }
                paragraph.alignment = alignment_map.get(text_alignment)

            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack={},
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "heading":  # noqa: S105
            if first_paragraph:
                paragraph = get_or_add_first_paragraph(text_frame)
                first_paragraph = False
            else:
                paragraph = text_frame.add_paragraph()

            if line_spacing is not None:
                paragraph.line_spacing = line_spacing
            if text_alignment is not None:
                from pptx.enum.text import PP_ALIGN  # noqa: PLC0415

                alignment_map = {
                    "left": PP_ALIGN.LEFT,
                    "center": PP_ALIGN.CENTER,
                    "right": PP_ALIGN.RIGHT,
                    "justify": PP_ALIGN.JUSTIFY,
                }
                paragraph.alignment = alignment_map.get(text_alignment)

            level = token.get("attrs", {}).get("level", 1)
            header_size = int(font_size * HEADER_SIZES.get(level, 1.0)) if font_size else int(24 * HEADER_SIZES.get(level, 1.0))

            process_inline_tokens(
                paragraph,
                tokens=token.get("children", []),
                formatting_stack={"bold": True},
                font_size=header_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
            )

        elif token_type == "list":  # noqa: S105
            first_paragraph = process_list(
                text_frame=text_frame,
                token=token,
                level=0,
                first_paragraph=first_paragraph,
                font_size=font_size,
                font_family=font_family,
                font_colour=font_colour,
                highlight_colour=highlight_colour,
                hyperlink_colour=hyperlink_colour,
                bullet_char=bullet_char,
                from_placeholder=from_placeholder,
            )

        elif token_type == "block_quote":  # noqa: S105
            # Process blockquote content with indentation
            for child in token.get("children", []):
                if child.get("type") == "paragraph":
                    if first_paragraph:
                        paragraph = get_or_add_first_paragraph(text_frame)
                        first_paragraph = False
                    else:
                        paragraph = text_frame.add_paragraph()

                    # Add quote indicator
                    run = paragraph.add_run()
                    run.text = "│ "
                    set_run_formatting(
                        run,
                        font_size=font_size,
                        font_family=font_family,
                        font_colour=Colour.parse("#666666"),
                    )

                    process_inline_tokens(
                        paragraph,
                        tokens=child.get("children", []),
                        formatting_stack={"italic": True},
                        font_size=font_size,
                        font_family=font_family,
                        font_colour=Colour.parse("#666666") if font_colour is None else font_colour,
                        highlight_colour=highlight_colour,
                        hyperlink_colour=hyperlink_colour,
                    )

        elif token_type == "block_code":  # noqa: S105
            if first_paragraph:
                paragraph = get_or_add_first_paragraph(text_frame)
                first_paragraph = False
            else:
                paragraph = text_frame.add_paragraph()

            code_text = token.get("raw", "").rstrip("\n")
            run = paragraph.add_run()
            run.text = code_text
            set_run_formatting(
                run,
                font_size=font_size or 10,
                font_family=CODE_FONT,
                font_colour=font_colour,
                highlight_colour=Colour.parse("#F5F5F5"),
            )

        elif token_type == "footnote_list":  # noqa: S105
            # Store footnotes for later processing
            for footnote in token.get("children", []):
                if footnote.get("type") == "footnote_item":
                    key = footnote.get("attrs", {}).get("key", "")
                    footnotes_content[key] = footnote.get("children", [])

        elif token_type == "thematic_break":  # noqa: S105
            if first_paragraph:
                paragraph = get_or_add_first_paragraph(text_frame)
                first_paragraph = False
            else:
                paragraph = text_frame.add_paragraph()

            run = paragraph.add_run()
            run.text = "─" * 40
            set_run_formatting(
                run,
                font_size=font_size,
                font_family=font_family,
                font_colour=Colour.parse("#CCCCCC"),
            )

        elif token_type == "blank_line":  # noqa: S105
            # Skip blank lines (they're just spacing in markdown)
            pass

    # Add footnotes at the end if any exist
    if footnotes_content:
        # Add separator
        paragraph = text_frame.add_paragraph()
        run = paragraph.add_run()
        run.text = "─" * 20
        set_run_formatting(
            run,
            font_size=font_size or 8,
            font_family=font_family,
            font_colour=Colour.parse("#999999"),
        )

        # Add each footnote
        for key, content in footnotes_content.items():
            paragraph = text_frame.add_paragraph()
            run = paragraph.add_run()
            run.text = f"[{key}] "
            set_run_formatting(
                run,
                font_size=(font_size - 2) if font_size else 8,
                font_family=font_family,
                font_colour=Colour.parse("#666666"),
                superscript=True,
            )

            for child in content:
                if child.get("type") == "paragraph":
                    process_inline_tokens(
                        paragraph,
                        tokens=child.get("children", []),
                        formatting_stack={},
                        font_size=(font_size - 2) if font_size else 8,
                        font_family=font_family,
                        font_colour=Colour.parse("#666666"),
                        highlight_colour=highlight_colour,
                        hyperlink_colour=hyperlink_colour,
                    )

    return text_frame
