from pathlib import Path
import fitz
from PIL import Image
import io


class Pdf(object):
    def __init__(
        self,
        pdf_path: str | Path,
    ):
        self.pdf_path = Path(pdf_path).expanduser().resolve()

        if not self.pdf_path.exists():
            raise FileNotFoundError(self.pdf_path)

    def show_images(
        self,
        zoom: float = 2.0,
    ):
        doc = fitz.open(filename=str(self.pdf_path))

        for i in range(doc.page_count):
            page = doc.load_page(i)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            try:
                from IPython.display import display

                display(img)

            except ImportError:
                img.show()

        doc.close()

    def _repr_html_(
        self,
    ):
        self.show_images(zoom=2.0)
