from PIL import Image

from .base import BrowserConverter

class Html2ImageConverter(BrowserConverter):
    def screenshot(self, html: str, ss_width: int = ..., ss_height: int = ...) -> Image: ...
