from rest_framework.exceptions import ValidationError

from apps.agency.models import Agency

# Every check the agency views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_name_free(name, exclude=None):
    # Agency.objects: a deleted agency's name may be reused.
    agencies = Agency.objects.filter(name__iexact=name)
    if exclude is not None:
        agencies = agencies.exclude(pk=exclude.pk)
    if agencies.exists():
        raise ValidationError({'name': ['An agency with this name already exists.']})


def ensure_npn_free(npn, exclude=None):
    if not npn:
        return
    agencies = Agency.objects.filter(npn=npn)
    if exclude is not None:
        agencies = agencies.exclude(pk=exclude.pk)
    if agencies.exists():
        raise ValidationError({'npn': ['An agency with this NPN already exists.']})
