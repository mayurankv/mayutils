from pathlib import Path
import subprocess
import streamlit as st
from streamlit import session_state as ss


class StreamlitManager(object):
    @staticmethod
    def initialise(
        **kwargs,
    ) -> None:
        for key, value in kwargs.items():
            if key not in ss:
                setattr(ss, key, value)

    @staticmethod
    def add_style(
        css: str,
    ) -> None:
        st.markdown(
            body=f"<style>{css}</style>",
            unsafe_allow_html=True,
        )

    @staticmethod
    def add_css(
        path: Path | str,
    ) -> None:
        path = Path(path)
        css = Path(path).read_text()
        StreamlitManager.add_style(css=css)

    @staticmethod
    def run() -> None:
        subprocess.run(args="poetry run streamlit run main.py")
