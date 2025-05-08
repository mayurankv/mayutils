from pathlib import Path
import streamlit as st
from streamlit import session_state as ss


class StreamlitManager(object):
    def __init__(
        self,
        **kwargs,
    ) -> None:
        for key, value in kwargs.items():
            if key not in ss:
                setattr(ss, key, value)

    def add_style(
        self,
        css: str,
    ) -> None:
        st.markdown(
            body=f"<style>{css}</style>",
            unsafe_allow_html=True,
        )

    def add_css(
        self,
        path: Path | str,
    ) -> None:
        path = Path(path)
        css = Path(path).read_text()
        self.add_style(css=css)
