from contextlib import contextmanager
from typing import Literal

import pandas as pd

MAX_COLS = ...
MAX_ROWS = ...

@contextmanager
def disable_max_image_pixels(): ...

@pd.api.extensions.register_dataframe_accessor("dfi")
class _Export:
    def __init__(self, df) -> None: ...
    def export(self, filename, fontsize=..., max_rows=..., max_cols=..., table_conversion=..., chrome_path=..., dpi=...): ...

BROWSER_CONVERTER_DICT = ...

def prepare_converter(
    filename,
    fontsize=...,
    max_rows=...,
    max_cols=...,
    table_conversion: Literal["chrome", "matplotlib", "html2image", "playwright", "selenium", "playwright_async"] = ...,
    chrome_path=...,
    dpi=...,
    use_mathjax=...,
    crop_top=...,
): ...
def generate_html(obj: pd.DataFrame, filename, max_rows=..., max_cols=...): ...
def save_image(img_str, filename): ...
def export(
    obj: pd.DataFrame,
    filename,
    fontsize=...,
    max_rows=...,
    max_cols=...,
    table_conversion: Literal["chrome", "matplotlib", "html2image", "playwright", "selenium"] = ...,
    chrome_path=...,
    dpi=...,
    use_mathjax=...,
    crop_top=...,
): ...
async def export_async(
    obj: pd.DataFrame,
    filename,
    fontsize=...,
    max_rows=...,
    max_cols=...,
    table_conversion: Literal["chrome", "matplotlib", "html2image", "playwright", "selenium", "playwright_async"] = ...,
    chrome_path=...,
    dpi=...,
    use_mathjax=...,
    crop_top=...,
): ...

accessor_intro = ...
styler_intro = ...
doc_params = ...
export_intro = ...
