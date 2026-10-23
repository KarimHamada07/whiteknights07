from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (ClothingModel, Customer, Expense, PurchaseInvoice,
                     PurchaseItem, SaleInvoice, SaleItem, Supplier, Variant)


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 3
    readonly_fields = ("quantity", "avg_cost")


@admin.register(ClothingModel)
class ClothingModelAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    inlines = [VariantInline]


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("model", "size", "color", "quantity", "avg_cost", "sale_price")
    list_filter = ("model",)
    readonly_fields = ("quantity", "avg_cost")


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1


def _confirm(modeladmin, request, queryset):
    for inv in queryset:
        try:
            inv.confirm()
            messages.success(request, f"تم تأكيد {inv}")
        except ValidationError as e:
            messages.error(request, f"{inv}: {' '.join(e.messages)}")


_confirm.short_description = "تأكيد الفواتير المحددة (تحديث المخزون)"


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "date", "total", "is_confirmed")
    inlines = [PurchaseItemInline]
    actions = [_confirm]


@admin.register(SaleInvoice)
class SaleInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "date", "total", "profit", "is_confirmed")
    inlines = [SaleItemInline]
    actions = [_confirm]


admin.site.register(Supplier)
admin.site.register(Customer)
admin.site.register(Expense)
