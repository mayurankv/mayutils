from streamlit import session_state as ss


class SessionState(object):
    @staticmethod
    def initialise(
        **kwargs,
    ) -> None:
        for key, value in kwargs.items():
            if key not in ss:
                setattr(ss, key, value)
