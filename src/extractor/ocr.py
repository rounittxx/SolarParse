# Tesseract is the fallback. We only call this when the PDF text layer
# was empty AND the user doesn't have the Gemini key set up (or the
# vision call failed). In practice with Gemini Flash this rarely runs,
# but it's nice to have a working offline path.

from PIL import Image

try:
    import pytesseract
    HAVE_TESSERACT = True
except ImportError:
    HAVE_TESSERACT = False


def ocr_image(img: Image.Image) -> str:
    if not HAVE_TESSERACT:
        return ""
    # psm 6 = "assume a single uniform block of text" -- works well on
    # the dense, table-like layout most utility bills use.
    return pytesseract.image_to_string(img, config="--psm 6")


def ocr_images(images: list[Image.Image]) -> str:
    return "\n\n".join(ocr_image(im) for im in images).strip()
