import asyncio
from io import BytesIO
from PIL import Image
import pytest
from app.face.images import decode_image
from app.face.types import FaceError
from app.services.uploads import receive_photo, stored_path


def picture(format='PNG', exif=None):
    output = BytesIO()
    kwargs = {'exif': exif} if exif else {}
    Image.new('RGB', (40, 20), 'red').save(output, format=format, **kwargs)
    return output.getvalue()


def test_decode_and_orientation():
    image = decode_image(picture())
    assert image.shape == (20, 40, 3)
    assert list(image[0, 0]) == [0, 0, 255]
    exif = Image.Exif(); exif[274] = 6
    assert decode_image(picture('JPEG', exif)).shape == (40, 20, 3)


@pytest.mark.parametrize('data,code', [(b'', 'INVALID_IMAGE'), (b'not a jpeg', 'INVALID_IMAGE'), (picture('GIF'), 'UNSUPPORTED_IMAGE'), (picture()[:20], 'INVALID_IMAGE')])
def test_invalid_images(data, code):
    with pytest.raises(FaceError) as error:
        decode_image(data)
    assert error.value.code == code


def test_size_limits():
    for limits in [{'max_bytes': 4}, {'max_pixels': 10}]:
        with pytest.raises(FaceError, match='IMAGE_TOO_LARGE'):
            decode_image(picture(), **limits)


def test_safe_upload_and_rejection(tmp_path):
    class Upload:
        filename = '../../.env'
        def __init__(self, data): self.stream=BytesIO(data); self.closed=False
        async def read(self, size): return self.stream.read(size)
        async def close(self): self.closed=True
    item=Upload(picture())
    result=asyncio.run(receive_photo(item, tmp_path))
    assert item.closed and stored_path(tmp_path, result.path).is_file()
    before=list(tmp_path.rglob('*'))
    with pytest.raises(FaceError): asyncio.run(receive_photo(Upload(b'invalid'), tmp_path))
    assert list(tmp_path.rglob('*')) == before
    with pytest.raises(ValueError): stored_path(tmp_path, '../outside')
