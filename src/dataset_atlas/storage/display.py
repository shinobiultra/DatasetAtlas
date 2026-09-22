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
