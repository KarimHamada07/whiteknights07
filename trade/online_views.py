import json
from decimal import Decimal, InvalidOperation

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import OnlineOrder, Variant

STATUS_STYLE = {
    OnlineOrder.PREPARED: "info",
    OnlineOrder.SHIPPED: "primary",
    OnlineOrder.COLLECTED: "success",
    OnlineOrder.RETURNED: "danger",
}


def _whatsapp_link(phone):
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("0") and len(digits) == 11:  # رقم مصري محلي
        digits = "2" + digits
    return f"https://wa.me/{digits}" if digits else ""


@staff_member_required
def online_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if status not in dict(OnlineOrder.STATUS_CHOICES):
        status = ""

    base = OnlineOrder.objects.all()
    if q:
        cond = Q(customer_name__icontains=q) | Q(phone__icontains=q)
        if q.isdigit() and len(q) <= 6:  # بحث برقم الأوردر
            cond |= Q(pk=int(q))
        base = base.filter(cond)

    counts = dict(base.values_list("status").annotate(c=Count("id")))
    tabs = [{"key": "", "label": "الكل", "count": sum(counts.values()),
             "style": "secondary", "active": status == ""}]
    for key, label in OnlineOrder.STATUS_CHOICES:
        tabs.append({"key": key, "label": label, "count": counts.get(key, 0),
                     "style": STATUS_STYLE[key], "active": status == key})

    qs = base.filter(status=status) if status else base
    qs = qs.prefetch_related("items__variant__model").order_by("-id")
    page = Paginator(qs, 20).get_page(request.GET.get("page"))

    orders = [{"order": o, "style": STATUS_STYLE[o.status]} for o in page]
    context = {
        **admin.site.each_context(request),
        "title": "الأونلاين",
        "orders": orders,
        "page": page,
        "tabs": tabs,
        "q": q,
        "status": status,
    }
    return render(request, "trade/online_list.html", context)


@staff_member_required
def online_new(request):
    variants = (Variant.objects
                .filter(model__is_active=True, quantity__gt=0)
                .select_related("model")
                .order_by("model__name", "size", "color"))
    data = [{
        "id": v.id, "name": v.model.name, "code": v.model.code,
        "size": v.size, "color": v.color, "qty": v.quantity,
        "price": float(v.sale_price),
    } for v in variants]
    context = {**admin.site.each_context(request), "title": "أوردر أونلاين جديد",
               "variants": data}
    return render(request, "trade/online_new.html", context)


def _money(value):
    try:
        return Decimal(str(value or 0))
    except InvalidOperation:
        raise ValueError("رقم غير صحيح")


@staff_member_required
@require_POST
def online_create(request):
    if not request.user.has_perm("trade.add_onlineorder"):
        return JsonResponse({"ok": False, "error": "مفيش صلاحية لإضافة أوردر"},
                            status=403)
    try:
        p = json.loads(request.body)
        order = OnlineOrder.create_order(
            customer_name=p.get("name", ""),
            phone=p.get("phone", ""),
            address=p.get("address", ""),
            notes=p.get("notes", ""),
            discount=_money(p.get("discount")),
            shipping_fee=_money(p.get("shipping_fee")),
            shipping_cost=_money(p.get("shipping_cost")),
            items=p.get("items") or [],
        )
    except ValidationError as e:
        return JsonResponse({"ok": False, "error": " ".join(e.messages)}, status=400)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "بيانات غير صحيحة"}, status=400)
    return JsonResponse({"ok": True,
                         "url": reverse("online_detail", args=[order.pk])})


@staff_member_required
def online_detail(request, pk):
    order = get_object_or_404(
        OnlineOrder.objects.prefetch_related("items__variant__model"), pk=pk)
    context = {
        **admin.site.each_context(request),
        "title": f"أوردر #{order.pk}",
        "order": order,
        "style": STATUS_STYLE[order.status],
        "rows": [{"item": i, "total": i.quantity * i.unit_price}
                 for i in order.items.all()],
        "next_actions": [(s, label, STATUS_STYLE[s])
                         for s, label in order.allowed_next],
        "wa_link": _whatsapp_link(order.phone),
    }
    return render(request, "trade/online_detail.html", context)


@staff_member_required
@require_POST
def online_status(request, pk):
    if not request.user.has_perm("trade.change_onlineorder"):
        raise PermissionDenied
    order = get_object_or_404(OnlineOrder, pk=pk)
    try:
        order.set_status(request.POST.get("status", ""))
        messages.success(
            request, f"تم تحديث الأوردر #{pk} إلى: {order.get_status_display()}")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("online_detail", pk=pk)
