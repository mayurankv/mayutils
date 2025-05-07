import json
from hashlib import md5


def hash_inputs(
    *args,
    **kwargs,
) -> str:
    return md5(
        string=json.dumps(
            obj={
                "args": args,
                "kwargs": kwargs,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
