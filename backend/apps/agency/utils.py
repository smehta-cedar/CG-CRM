from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.agency.models import Agency

# Helpers the agency views share. Checks that can reject a request live in
# apps.agency.validators instead.


def get_agency_or_404(pk):
    return get_object_or_404(Agency.objects, pk=pk)


def normalize_name(name):
    return ' '.join(name.split())


def normalize_npn(npn):
    return npn.strip()


def normalize_email(email):
    return email.strip().lower()


def normalize_aliases(aliases):
    """Trim each alias, drop blanks, and keep the first of any duplicates
    (compared case-insensitively) in the order given."""
    seen = set()
    result = []
    for alias in aliases:
        alias = ' '.join(alias.split())
        key = alias.lower()
        if alias and key not in seen:
            seen.add(key)
            result.append(alias)
    return result


def search_agencies(agencies, search):
    """Narrow `agencies` to those whose name, alias, NPN, email or phone matches."""
    return agencies.filter(
        Q(name__icontains=search)
        | Q(aliases__icontains=search)
        | Q(npn__icontains=search)
        | Q(email__icontains=search)
        | Q(phone__icontains=search)
    )


def filter_agencies(agencies, is_active=None):
    """Narrow `agencies` by is_active; None means no filter."""
    if is_active is not None:
        agencies = agencies.filter(is_active=is_active)
    return agencies


def save_agency(agency, actor, **fields):
    """Set `fields` on the agency and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(agency, name, value)
    agency.updated_by = actor
    agency.save(update_fields=[*fields, 'updated_by'])
    return agency
