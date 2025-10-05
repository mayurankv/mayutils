import json
from hashlib import md5
from mayutils.objects.datetime import DateTime
from pendulum import DateTime as PendulumDateTime
from datetime import datetime


def serialise(
    obj,
) -> str:
    if isinstance(obj, (DateTime, PendulumDateTime, datetime)):
        return obj.isoformat()

    raise TypeError(f"Type {type(obj)} not serialisable")


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
            default=serialise,
        ).encode()
    ).hexdigest()
