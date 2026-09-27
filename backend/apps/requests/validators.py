from rest_framework.exceptions import ValidationError

from apps.agency.models import State

# Every check the request views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def resolve_state(code):
    """The State row for a two-letter code (any case). An unknown code is a 400."""
    state = State.objects.filter(code=(code or '').strip().upper()).first()
    if state is None:
        raise ValidationError({'state': [f'Unknown state code: {code}.']})
    return state


def ensure_fields_for_type(data):
    """A licensing or contract request needs a state and a carrier; a day off
    needs its dates, with the last day on or after the first."""
    request_type = data['type']
    if request_type in ('licensing', 'contract'):
        if not data.get('state'):
            raise ValidationError({'state': ['Choose a state.']})
        if not data.get('carrier'):
            raise ValidationError({'carrier_id': ['Choose a carrier.']})
    elif request_type == 'day_off':
        if not data.get('start_date'):
            raise ValidationError({'start_date': ['Enter the first day off.']})
        if not data.get('end_date'):
            raise ValidationError({'end_date': ['Enter the last day off.']})
        if data['end_date'] < data['start_date']:
            raise ValidationError({'end_date': ["The last day can't be before the first."]})
