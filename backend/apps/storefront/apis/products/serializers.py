from rest_framework import serializers

from apps.storefront.models import PRODUCT_CATEGORIES, PRODUCT_TYPES, Product, ProductNote
from apps.storefront.utils import normalize_colors, normalize_sizes


class ColorSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=50, required=False, allow_blank=True, help_text='Left out, it is made from the label.')
    label = serializers.CharField(max_length=50)
    hex = serializers.RegexField(
        r'^#[0-9a-fA-F]{6}$',
        error_messages={'invalid': 'Enter a colour like #37b38f.'},
    )


class ProductSerializer(serializers.ModelSerializer):
    """How a product appears in every response, the public catalog included."""

    colors = ColorSerializer(many=True, read_only=True)
    sizes = serializers.ListField(child=serializers.CharField(), read_only=True)
    price = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True, coerce_to_string=False)

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'description',
            'category',
            'product_type',
            'image_url',
            'price',
            'colors',
            'sizes',
            'max_quantity',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class ProductSummarySerializer(serializers.ModelSerializer):
    """A product as an order names it."""

    class Meta:
        model = Product
        fields = ('id', 'name', 'is_active')


class ProductChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class ProductNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    product_id = serializers.UUIDField(read_only=True)
    changes = ProductChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = ProductNote
        fields = ('id', 'product_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


def _colors_field(required):
    return serializers.ListField(child=ColorSerializer(), required=required, help_text='At least one.')


def _sizes_field(required):
    return serializers.ListField(
        child=serializers.CharField(max_length=20, allow_blank=True), required=required, help_text='At least one, in display order.'
    )


class _ProductWriteSerializer(serializers.Serializer):
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=PRODUCT_CATEGORIES, required=False, allow_blank=True)
    product_type = serializers.ChoiceField(choices=PRODUCT_TYPES, required=False, allow_blank=True)
    image_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    max_quantity = serializers.IntegerField(required=False, min_value=1, max_value=999)
    is_active = serializers.BooleanField(required=False)

    def validate_colors(self, value):
        return normalize_colors(value)

    def validate_sizes(self, value):
        return normalize_sizes(value)


class ProductCreateSerializer(_ProductWriteSerializer):
    name = serializers.CharField(max_length=255)
    price = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)
    colors = _colors_field(required=True)
    sizes = _sizes_field(required=True)


class ProductUpdateSerializer(_ProductWriteSerializer):
    """Send only the fields that change."""

    name = serializers.CharField(max_length=255, required=False)
    price = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0, required=False)
    colors = _colors_field(required=False)
    sizes = _sizes_field(required=False)


class ProductListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, help_text='Matches name or description.')
    is_active = serializers.BooleanField(required=False, allow_null=True)
    category = serializers.ChoiceField(choices=PRODUCT_CATEGORIES, required=False, allow_blank=True)
    product_type = serializers.ChoiceField(choices=PRODUCT_TYPES, required=False, allow_blank=True)
