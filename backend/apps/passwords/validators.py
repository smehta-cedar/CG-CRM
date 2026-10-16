from rest_framework.exceptions import ValidationError

from apps.passwords.models import Password, Site, SitePassword

# Every check the password views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_one_party(agent, agency):
    """A password belongs to an agent or the agency: exactly one."""
    if (agent is None) == (agency is None):
        raise ValidationError({'agent_id': ['Choose an agent or the agency.']})


def ensure_pair_free(carrier, agent=None, agency=None, exclude=None):
    """One password per agent at each carrier, and one for the agency."""
    passwords = Password.objects.filter(carrier=carrier, agent=agent, agency=agency)
    if exclude is not None:
        passwords = passwords.exclude(pk=exclude.pk)
    if passwords.exists():
        party = agent or agency
        raise ValidationError({'carrier_id': [f'{party.name} already has a password at {carrier.name}.']})


def ensure_credentials(status, username, portal_password):
    """The portal username and password are required, spaces alone not
    counting, unless the status is pending (the login isn't issued yet). A
    valid password is saved as typed."""
    if status == 'pending':
        return
    errors = {}
    if username.strip() == '':
        errors['username'] = ["Username can't be blank."]
    if portal_password.strip() == '':
        errors['portal_password'] = ["Password can't be blank."]
    if errors:
        raise ValidationError(errors)


def ensure_site_name_free(name, exclude=None):
    """Site names are unique among live sites, whatever their case."""
    sites = Site.objects.filter(name__iexact=name.strip())
    if exclude is not None:
        sites = sites.exclude(pk=exclude.pk)
    if sites.exists():
        raise ValidationError({'name': ['A site with this name already exists.']})


def ensure_site_unused(site):
    """A site with live passwords can't be deleted."""
    if site.passwords.exists():
        raise ValidationError({'site': ['Delete or move the passwords at this site first.']})


def ensure_site_pair_free(site, agent=None, agency=None, exclude=None):
    """One site password per agent at each site, and one for the agency."""
    passwords = SitePassword.objects.filter(site=site, agent=agent, agency=agency)
    if exclude is not None:
        passwords = passwords.exclude(pk=exclude.pk)
    if passwords.exists():
        party = agent or agency
        raise ValidationError({'site_id': [f'{party.name} already has a password at {site.name}.']})
