import json
from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Customer, SaleInvoice, SaleItem, Variant


@staff_member_required
def pos(request):
    variants = (Variant.objects
                .filter(model__is_active=True, quantity__gt=0)
                .select_related("model")
                .order_by("model__name", "size", "color"))
    data = [{
        "id": v.id,
        "name": v.model.name,
        "code": v.model.code,
        "size": v.size,
        "color": v.color,
        "qty": v.quantity,
        "price": float(v.sale_price),
    } for v in variants]
    context = {
        **admin.site.each_context(request),
        "title": "بيع سريع",
        "variants": data,
        "customers": Customer.objects.order_by("name"),
    }
    return render(request, "trade/pos.html", context)


@staff_member_required
@require_POST
def pos_checkout(request):
    try:
        payload = json.loads(request.body)
        items = payload.get("items") or []
        if not items:
            raise ValidationError("السلة فاضية")
        discount = Decimal(str(payload.get("discount") or 0))
        if discount < 0:
            raise ValidationError("الخصم غير صحيح")

        with transaction.atomic():
            customer = None
            if payload.get("customer"):
                customer = Customer.objects.filter(pk=payload["customer"]).first()
            invoice = SaleInvoice.objects.create(
                customer=customer,
                date=timezone.localdate(),
                discount=discount,
                notes="بيع سريع",
            )
            gross = Decimal("0")
            for it in items:
                qty = int(it["qty"])
                price = Decimal(str(it["price"]))
                if qty <= 0 or price < 0:
                    raise ValidationError("كمية أو سعر غير صحيح")
                variant = Variant.objects.get(pk=it["id"])
                SaleItem.objects.create(invoice=invoice, variant=variant,
                                        quantity=qty, unit_price=price)
                gross += qty * price
            if discount > gross:
                raise ValidationError("الخصم أكبر من إجمالي الفاتورة")
            invoice.confirm()  # يخصم المخزون ويثبت التكلفة

    except ValidationError as e:
        return JsonResponse({"ok": False, "error": " ".join(e.messages)}, status=400)
    except (ValueError, TypeError, KeyError, InvalidOperation,
            Variant.DoesNotExist, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "بيانات غير صحيحة"}, status=400)

    return JsonResponse({
        "ok": True,
        "id": invoice.id,
        "print_url": reverse("sale_print", args=[invoice.id]),
    })


@staff_member_required
def sale_print(request, pk):
    invoice = get_object_or_404(
        SaleInvoice.objects.select_related("customer"), pk=pk)
    rows = [{
        "name": str(i.variant),
        "qty": i.quantity,
        "price": i.unit_price,
        "total": i.quantity * i.unit_price,
    } for i in invoice.items.select_related("variant", "variant__model")]
    gross = sum((r["total"] for r in rows), Decimal("0"))
    return render(request, "trade/invoice_print.html", {
        "invoice": invoice,
        "rows": rows,
        "gross": gross,
        "total": gross - invoice.discount,
        "shop_name": "Ultras White Knights",
    })
