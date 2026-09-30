from rest_framework.exceptions import ValidationError

from apps.passwords.models import Password

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


def ensure_password_not_blank(portal_password):
    """Required, and spaces alone don't count. A valid password is saved as typed."""
    if portal_password.strip() == '':
        raise ValidationError({'portal_password': ["Password can't be blank."]})
