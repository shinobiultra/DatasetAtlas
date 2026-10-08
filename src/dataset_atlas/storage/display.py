"""Display-only image derivatives. Never used by processor or provider inputs."""
import io
from PIL import Image, ImageFilter, ImageOps


def safe_view(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 50_000_000:
            raise ValueError('Display derivative exceeds pixel budget')
        image = ImageOps.exif_transpose(source).convert('RGB')
        size = image.size
        image.thumbnail((12, 12), Image.Resampling.BOX)
        image = image.resize(size, Image.Resampling.NEAREST).filter(ImageFilter.GaussianBlur(max(size) / 40))
        result = io.BytesIO()
        image.save(result, format='PNG')
        return result.getvalue()


def browser_render(data: bytes, max_edge: int = 4096) -> bytes:
    """A faithful, bounded PNG rendering of an image a browser cannot decode (TIFF). Display only: the original bytes stay the asset.

    16-bit and floating-point samples are scaled linearly to 8 bits over their full range; alpha is kept; nothing is blurred or
    cropped. Nonfinite floating-point samples fail explicitly. An image whose longer edge exceeds `max_edge` is shrunk to that edge so one request stays bounded."""
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 50_000_000:
            raise ValueError('Display rendering exceeds pixel budget')
        image = ImageOps.exif_transpose(source)
        if image.mode in ('I;16', 'I;16L', 'I;16B', 'I', 'F'):
            import numpy as np
            array = np.asarray(image, dtype='float64')
            if not np.isfinite(array).all():raise ValueError('Display rendering requires finite pixel samples')
            low, high = float(array.min()), float(array.max())
            scaled = np.zeros_like(array) if high == low else (array - low) * (255.0 / (high - low))
            image = Image.fromarray(scaled.astype('uint8'), mode='L')
        elif image.mode not in ('L', 'RGB', 'RGBA', 'LA'):
            image = image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
        if max(image.size) > max_edge:
            image = image.copy()
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        result = io.BytesIO()
        image.save(result, format='PNG')
        return result.getvalue()
