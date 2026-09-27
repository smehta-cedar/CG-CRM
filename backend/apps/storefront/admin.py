from django.contrib import admin

from .models import Product, ProductNote

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


class ProductNoteInline(admin.TabularInline):
    model = ProductNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'colour_labels', 'size_labels', 'max_quantity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = AUDIT_FIELDS
    inlines = (ProductNoteInline,)

    @admin.display(description='Colours')
    def colour_labels(self, product):
        return ', '.join(color['label'] for color in product.colors)

    @admin.display(description='Sizes')
    def size_labels(self, product):
        return ', '.join(product.sizes)
