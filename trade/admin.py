from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (ClothingModel, CustodyDeposit, CustodySettlement, Customer,
                     Expense, OnlineOrder, OnlineOrderItem, Payment,
                     PurchaseInvoice, PurchaseItem, SaleInvoice, SaleItem,
                     Supplier, Variant)


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
    list_display = ("id", "customer", "date", "payment_type", "total", "profit",
                    "is_confirmed")
    list_filter = ("payment_type", "is_confirmed")
    inlines = [SaleItemInline]
    actions = [_confirm]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone")
    search_fields = ("name", "phone")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("customer", "amount", "date", "method", "invoice")
    list_filter = ("method",)
    search_fields = ("customer__name", "customer__phone")


class OnlineOrderItemInline(admin.TabularInline):
    model = OnlineOrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("variant", "quantity", "unit_price", "unit_cost")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OnlineOrder)
class OnlineOrderAdmin(admin.ModelAdmin):
    """للاطلاع والبحث فقط. الإنشاء وتغيير الحالة من صفحة الأونلاين لحماية المخزون"""
    list_display = ("id", "customer_name", "phone", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("customer_name", "phone")
    inlines = [OnlineOrderItemInline]
    readonly_fields = ("status", "discount", "shipping_fee", "shipping_cost",
                       "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


admin.site.register(Supplier)
admin.site.register(Expense)


@admin.register(CustodySettlement)
class CustodySettlementAdmin(admin.ModelAdmin):
    """للاطلاع فقط. التسجيل من صفحة العهدة (فيها فحص الصورة والمبالغ)"""
    list_display = ("id", "amount", "received_by", "method", "settled_at", "proof")
    search_fields = ("received_by", "notes")
    list_filter = ("method",)
    exclude = ("screenshot",)
    readonly_fields = ("amount", "received_by", "method", "settled_at", "notes",
                       "created_by", "created_at")

    @admin.display(boolean=True, description="إثبات")
    def proof(self, obj):
        return obj.has_proof

    def has_add_permission(self, request):
        return False


@admin.register(CustodyDeposit)
class CustodyDepositAdmin(admin.ModelAdmin):
    list_display = ("id", "amount", "date", "note", "created_by")
