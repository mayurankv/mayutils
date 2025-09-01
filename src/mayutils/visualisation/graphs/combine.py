import pymupdf
from PIL import Image


def combine_figures(
    files: list[str],
    title: str,
    cols: int,
    rows: int,
    filetype: str = "pdf",
) -> None:
    if filetype == "pdf":
        images = []
        for file in files:
            doc = pymupdf.open(file)
            pix = doc[0].get_pixmap()  # type: ignore
            img = Image.frombytes(
                mode="RGB",
                size=(
                    pix.width,
                    pix.height,
                ),
                data=pix.samples,
            )
            images.append(img)

        img_width, img_height = images[0].size

        final_image = Image.new(
            mode="RGB",
            size=(
                img_width * cols,
                img_height * rows,
            ),
            color="white",
        )

        for idx, img in enumerate(images):
            row, col = divmod(idx, cols)
            final_image.paste(
                im=img,
                box=(
                    col * img_width,
                    row * img_height,
                ),
            )

        final_image.save(fp=f"{title}")

    else:
        raise NotImplementedError("Other conversions are not supported yet")
