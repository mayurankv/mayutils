def prettify(
    num: float,
) -> str:
    if num == 0:
        return "0"

    num = float("{:.3g}".format(num))
    pos_magnitude = 0
    neg_magnitude = 0

    while abs(num) >= 1000:
        pos_magnitude += 1
        num /= 1000.0

    while abs(num) <= 0.001:
        neg_magnitude += 1
        num *= 1000.0

    try:
        if pos_magnitude > 0:
            suffix = [
                "",
                "K",
                "M",
                "B",
                "T",
                "Qa",
                "Qi",
                "Sx",
                "Sp",
                "Oc",
                "No",
                "Dc",
            ][pos_magnitude]
        elif neg_magnitude > 0:
            suffix = [
                "",
                "m",
                "µ",
                "n",
                "p",
                "f",
                "a",
                "z",
                "y",
            ][neg_magnitude]
        else:
            suffix = ""

    except IndexError:
        raise

    return "{}{}".format("{:f}".format(num).rstrip("0").rstrip("."), suffix)
