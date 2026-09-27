from rest_framework.exceptions import ValidationError

from apps.agency.models import State
from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.policies.models import CarrierPolicy, Certification, PolicyType

# Every check the policies views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


# --- policy types -----------------------------------------------------------


def ensure_name_free(name, exclude=None):
    """A name can't repeat another live policy type's name, ignoring case."""
    policy_types = PolicyType.objects.all()
    if exclude is not None:
        policy_types = policy_types.exclude(pk=exclude.pk)
    if policy_types.filter(name__iexact=name).exists():
        raise ValidationError({'name': ['A policy type with this name already exists.']})


# --- carrier policies -------------------------------------------------------


def resolve_carrier(pk):
    """The live carrier with `pk`; an unknown one is a 400 under "carrier"."""
    carrier = Carrier.objects.prefetch_related('available_states').filter(pk=pk).first()
    if carrier is None:
        raise ValidationError({'carrier': ['Unknown carrier.']})
    return carrier


def resolve_policy_type(pk):
    """The live policy type with `pk`; an unknown one is a 400 under "policy_type"."""
    policy_type = PolicyType.objects.filter(pk=pk).first()
    if policy_type is None:
        raise ValidationError({'policy_type': ['Unknown policy type.']})
    return policy_type


def ensure_policy_name_free(carrier, name, exclude=None):
    """A name can't repeat another of the carrier's live policies, ignoring
    case. Another carrier may use the same name."""
    policies = CarrierPolicy.objects.filter(carrier=carrier)
    if exclude is not None:
        policies = policies.exclude(pk=exclude.pk)
    if policies.filter(name__iexact=name).exists():
        raise ValidationError({'name': ['This carrier already has a policy with this name.']})


def resolve_policy_states(codes, carrier):
    """The State rows for `codes` (two-letter, any case). Unknown codes and
    codes outside the carrier's available states are a 400 that names them."""
    wanted = {code.strip().upper() for code in codes if code and code.strip()}
    states = list(State.objects.filter(code__in=wanted))
    unknown = sorted(wanted - {state.code for state in states})
    if unknown:
        raise ValidationError({'available_states': [f"Unknown state code: {', '.join(unknown)}."]})
    outside = sorted(wanted - set(carrier.state_codes))
    if outside:
        raise ValidationError({'available_states': [f"{carrier.name} is not available in {', '.join(outside)}."]})
    return states


# --- certifications ---------------------------------------------------------


def resolve_agent(pk):
    """The live agent with `pk`; an unknown one is a 400 under "agent"."""
    agent = Agent.objects.filter(pk=pk).first()
    if agent is None:
        raise ValidationError({'agent': ['Unknown agent.']})
    return agent


def ensure_pair_free(agent, policy_type, field, exclude=None):
    """One live certification per agent and policy type. `field` is where the
    error sits: "policy_type" when the agent was already chosen, "agent" when
    the policy type was."""
    certifications = Certification.objects.filter(agent=agent, policy_type=policy_type)
    if exclude is not None:
        certifications = certifications.exclude(pk=exclude.pk)
    if certifications.exists():
        raise ValidationError({field: [f'{agent.name} is already certified for {policy_type.name}.']})


def ensure_dates_in_order(start_date, end_date):
    """When both dates are set, the end is on or after the start."""
    if start_date and end_date and end_date < start_date:
        raise ValidationError({'end_date': ['The end date must be on or after the start date.']})


# A certification's PDF: the one file type the API takes, up to this size.
MAX_CERTIFICATION_FILE_SIZE = 10 * 1024 * 1024


def ensure_pdf(upload):
    """The upload is a PDF (by name and by its first bytes) of at most 10 MB;
    anything else is a 400 under "file"."""
    if upload.size > MAX_CERTIFICATION_FILE_SIZE:
        raise ValidationError({'file': ['The file must be 10 MB or smaller.']})
    header = upload.read(5)
    upload.seek(0)
    if not upload.name.lower().endswith('.pdf') or header != b'%PDF-':
        raise ValidationError({'file': ['The file must be a PDF.']})
