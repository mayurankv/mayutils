from .base import BrowserConverter

class PlayWrightConverter(BrowserConverter):
    def __init__(
        self,
        center_df=...,
        max_rows=...,
        max_cols=...,
        chrome_path=...,
        fontsize=...,
        encode_base64=...,
        crop_top=...,
        device_scale_factor=...,
        use_mathjax=...,
    ) -> None: ...
    def screenshot(self, html): ...

class AsyncPlayWrightConverter(BrowserConverter):
    def __init__(
        self,
        center_df=...,
        max_rows=...,
        max_cols=...,
        chrome_path=...,
        fontsize=...,
        encode_base64=...,
        crop_top=...,
        device_scale_factor=...,
        use_mathjax=...,
    ) -> None: ...
    async def run(self, html: str) -> bytes: ...
    async def screenshot(self, html): ...
