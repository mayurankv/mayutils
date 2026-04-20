from PIL import Image

from .base import BrowserConverter

class SeleniumConverter(BrowserConverter):
    def screenshot(self, html: str) -> Image: ...
