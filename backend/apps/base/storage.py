import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible(path='apps.base.storage.PrivateStorage')
class PrivateStorage(FileSystemStorage):
    """Files that are never served by URL: they live under
    PRIVATE_MEDIA_ROOT and only an API view that checks permissions hands
    them out (e.g. GET /certifications/{id}/file/).

    The location is read from settings on every use, so a test can point it
    at a temporary folder with override_settings.
    """

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError('Private files have no public URL.')
