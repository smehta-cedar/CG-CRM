from rest_framework.exceptions import ValidationError

from apps.passwords.models import Password

# Every check the password views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_pair_free(agent, carrier, exclude=None):
    """One password per agent at each carrier."""
    passwords = Password.objects.filter(agent=agent, carrier=carrier)
    if exclude is not None:
        passwords = passwords.exclude(pk=exclude.pk)
    if passwords.exists():
        raise ValidationError({'carrier_id': [f'{agent.name} already has a password at {carrier.name}.']})


def ensure_password_not_blank(portal_password):
    """Required, and spaces alone don't count. A valid password is saved as typed."""
    if portal_password.strip() == '':
        raise ValidationError({'portal_password': ["Password can't be blank."]})
