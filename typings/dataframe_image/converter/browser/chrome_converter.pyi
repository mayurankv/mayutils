from dataframe_image.converter.browser.base import BrowserConverter
from PIL import Image

def get_system(): ...
def get_chrome_path(chrome_path=...): ...

class ChromeConverter(BrowserConverter):
    def __init__(
        self,
        center_df: bool = ...,
        max_rows: int = ...,
        max_cols: int = ...,
        chrome_path: str = ...,
        fontsize: int = ...,
        encode_base64: bool = ...,
        crop_top: bool = ...,
        device_scale_factor: int = ...,
        use_mathjax: bool = ...,
    ) -> None: ...
    def screenshot(self, html, ss_width=..., ss_height=...) -> Image: ...

def make_repr_png(center_df=..., max_rows=..., max_cols=..., chrome_path=...): ...
