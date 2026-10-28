from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ClothingModel, PurchaseInvoice

DEC = DecimalField(max_digits=14, decimal_places=2)
LOW_STOCK = 5  # نفس الحد المستخدم في لوحة التحكم

SIZE_ORDER = {
    "XXS": 0, "XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5,
    "XXL": 6, "2XL": 6, "XXXL": 7, "3XL": 7, "4XL": 8,
    "FREE": 9, "FREE SIZE": 9,
}


def _size_key(variant):
    """ترتيب منطقي للمقاسات: S, M, L, XL ثم الأرقام ثم أي نص آخر"""
    s = variant.size.strip().upper()
    if s in SIZE_ORDER:
        return (0, SIZE_ORDER[s], "", variant.color)
    try:
        return (1, float(s), "", variant.color)
    except ValueError:
        return (2, 0, s, variant.color)


@staff_member_required
def inventory(request):
    models_qs = (ClothingModel.objects
                 .annotate(
                     total_qty=Coalesce(Sum("variants__quantity"), 0),
                     variants_count=Count("variants", distinct=True),
                     low_variants=Count(
                         "variants",
                         filter=Q(variants__quantity__lte=LOW_STOCK),
                         distinct=True),
                     stock_value=Coalesce(
                         Sum(F("variants__quantity") * F("variants__avg_cost"),
                             output_field=DEC),
                         Decimal("0"), output_field=DEC),
                 )
                 .order_by("name"))
    items = list(models_qs)

    context = {
        **admin.site.each_context(request),
        "title": "المخزون",
        "items": items,
        "grand_qty": sum(m.total_qty for m in items),
        "grand_value": sum((m.stock_value for m in items), Decimal("0")),
        "models_count": len(items),
        "low_total": sum(m.low_variants for m in items),
        "low_limit": LOW_STOCK,
    }
    return render(request, "trade/inventory.html", context)


@staff_member_required
def inventory_detail(request, pk):
    model = get_object_or_404(ClothingModel, pk=pk)
    variants = sorted(model.variants.all(), key=_size_key)

    rows = []
    for v in variants:
        if v.quantity <= 0:
            status = "out"
        elif v.quantity <= LOW_STOCK:
            status = "low"
        else:
            status = "ok"
        rows.append({
            "variant": v,
            "value": v.quantity * v.avg_cost,
            "status": status,
        })

    total_qty = sum(r["variant"].quantity for r in rows)
    max_qty = max([r["variant"].quantity for r in rows], default=0) or 1
    for r in rows:
        r["percent"] = int(r["variant"].quantity * 100 / max_qty)

    context = {
        **admin.site.each_context(request),
        "title": model.name,
        "model": model,
        "rows": rows,
        "total_qty": total_qty,
        "total_value": sum((r["value"] for r in rows), Decimal("0")),
        "low_limit": LOW_STOCK,
    }
    return render(request, "trade/inventory_detail.html", context)


@staff_member_required
@require_POST
def purchase_confirm(request, pk):
    """تأكيد استلام فاتورة توريد من لوحة التحكم (يحدّث المخزون)"""
    if not request.user.has_perm("trade.change_purchaseinvoice"):
        raise PermissionDenied
    try:
        with transaction.atomic():
            invoice = PurchaseInvoice.objects.select_for_update().get(pk=pk)
            invoice.confirm()
        messages.success(
            request, f"تم تأكيد فاتورة التوريد #{pk} وتحديث المخزون")
    except PurchaseInvoice.DoesNotExist:
        messages.error(request, "الفاتورة غير موجودة")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    except ZeroDivisionError:
        messages.error(request, "الفاتورة فيها بند كميته صفر، عدّله ثم أكّد")
    return redirect("dashboard")
