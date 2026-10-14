from rest_framework import serializers

from apps.agency.models import Agency
from apps.agents.models import Agent
from apps.passwords.models import PASSWORD_STATUSES, Site, SitePassword, SitePasswordNote

from ..passwords.serializers import AgencySummarySerializer, AgentSummarySerializer, PasswordNoteSerializer
from ..sites.serializers import SiteSummarySerializer


class SitePasswordSerializer(serializers.ModelSerializer):
    """How a site password appears in every response. `agent` or `agency` is
    set, the other null. The portal password is included, like Password."""

    agent = AgentSummarySerializer(read_only=True)
    agency = AgencySummarySerializer(read_only=True)
    site = SiteSummarySerializer(read_only=True)
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, read_only=True)

    class Meta:
        model = SitePassword
        fields = (
            'id',
            'agent',
            'agency',
            'site',
            'username',
            'portal_password',
            'status',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class SitePasswordNoteSerializer(PasswordNoteSerializer):
    """Same shape as a carrier password's note."""

    class Meta(PasswordNoteSerializer.Meta):
        model = SitePasswordNote


# The querysets are lazy and re-run on every request. Only live sites can be
# chosen. A site password takes agent_id or agency_id: the other is null or
# left out.
def _agent_id_field():
    return serializers.PrimaryKeyRelatedField(
        source='agent', queryset=Agent.objects.all(), pk_field=serializers.UUIDField(), required=False, allow_null=True
    )


def _agency_id_field():
    return serializers.PrimaryKeyRelatedField(
        source='agency', queryset=Agency.objects.all(), pk_field=serializers.UUIDField(), required=False, allow_null=True
    )


def _site_id_field(required):
    return serializers.PrimaryKeyRelatedField(
        source='site', queryset=Site.objects.all(), pk_field=serializers.UUIDField(), required=required
    )


def _portal_password_field(required):
    # Not trimmed: spaces and case can matter in a password.
    return serializers.CharField(max_length=255, required=required, allow_blank=True, trim_whitespace=False)


class SitePasswordCreateSerializer(serializers.Serializer):
    """Send agent_id or agency_id, not both."""

    agent_id = _agent_id_field()
    agency_id = _agency_id_field()
    site_id = _site_id_field(required=True)
    # Blank only while the status is pending; the view checks that.
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)
    portal_password = _portal_password_field(required=False)
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, required=False)


class SitePasswordUpdateSerializer(serializers.Serializer):
    """Send only the fields that change. Setting agent_id clears the agency,
    and the other way round."""

    agent_id = _agent_id_field()
    agency_id = _agency_id_field()
    site_id = _site_id_field(required=False)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)
    portal_password = _portal_password_field(required=False)
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, required=False)


class SitePasswordListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False, allow_blank=True, help_text='Matches portal username, agent or agency name, or site name.'
    )
    agent_id = serializers.UUIDField(required=False)
    agency_id = serializers.UUIDField(required=False)
    site_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, required=False, allow_blank=True)
