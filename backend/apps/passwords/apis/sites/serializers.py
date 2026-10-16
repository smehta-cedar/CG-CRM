from rest_framework import serializers

from apps.passwords.models import Site


class SiteSerializer(serializers.ModelSerializer):
    """A site as every response shows it."""

    password_count = serializers.IntegerField(read_only=True, help_text='Live site passwords at this site.')

    class Meta:
        model = Site
        fields = ('id', 'name', 'link', 'password_count', 'created_at', 'updated_at')
        read_only_fields = fields


class SiteSummarySerializer(serializers.ModelSerializer):
    """The site as a site password nests it."""

    class Meta:
        model = Site
        fields = ('id', 'name', 'link')


class SiteWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    link = serializers.URLField(
        max_length=2000, required=False, allow_blank=True, help_text="The site's sign-in page. Blank for none."
    )


class SiteListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, help_text='Matches the site name.')
