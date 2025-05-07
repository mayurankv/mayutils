from streamlit import session_state as ss


class StreamlitState(object):
    def __init__(
        **kwargs,
    ) -> None:
        for key, value in kwargs.items():
            if key not in ss:
                setattr(ss, key, value)
