from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, DecimalField, F, Sum
from django.shortcuts import render
from django.utils import timezone

from .models import (ClothingModel, Customer, Expense, OnlineOrder,
                     PurchaseInvoice, SaleInvoice, SaleItem, Variant)
from .custody_views import custody_summary
from .stock_views import _size_key

LOW_STOCK = 5  # أي صنف كميته أقل من أو تساوي الرقم ده يظهر في التنبيهات
DEC = DecimalField(max_digits=14, decimal_places=2)


def _period(start, end):
    """مبيعات وربح فترة (فواتير مؤكدة فقط)"""
    items = SaleItem.objects.filter(
        invoice__is_confirmed=True, invoice__date__range=(start, end))
    agg = items.aggregate(
        rev=Sum(F("quantity") * F("unit_price"), output_field=DEC),
        cost=Sum(F("quantity") * F("unit_cost"), output_field=DEC),
        pcs=Sum("quantity"),
    )
    invoices = SaleInvoice.objects.filter(
        is_confirmed=True, date__range=(start, end))
    discount = invoices.aggregate(d=Sum("discount"))["d"] or 0
    revenue = (agg["rev"] or 0) - discount
    profit = revenue - (agg["cost"] or 0)
    pieces = agg["pcs"] or 0

    # الأونلاين: التحصيل بيدخل المبيعات والربح، والمرتجع بيخصم تكلفة الشحن
    online = (OnlineOrder.objects
              .filter(status__in=[OnlineOrder.COLLECTED, OnlineOrder.RETURNED],
                      updated_at__date__range=(start, end))
              .prefetch_related("items"))
    for o in online:
        profit += o.profit
        if o.status == OnlineOrder.COLLECTED:
            revenue += o.items_total - o.discount
            pieces += o.pieces

    return {
        "revenue": revenue,
        "profit": profit,
        "pieces": pieces,
        "invoices": invoices.count(),
    }


@staff_member_required
def dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)

    today_stats = _period(today, today)
    month_stats = _period(month_start, today)

    month_expenses = Expense.objects.filter(
        date__range=(month_start, today)).aggregate(s=Sum("amount"))["s"] or 0
    net_profit = month_stats["profit"] - month_expenses

    stock = Variant.objects.aggregate(
        value=Sum(F("quantity") * F("avg_cost"), output_field=DEC),
        pieces=Sum("quantity"),
    )

    low_stock = (Variant.objects
                 .filter(quantity__lte=LOW_STOCK, model__is_active=True)
                 .select_related("model")
                 .order_by("quantity")[:10])

    top_models = (SaleItem.objects
                  .filter(invoice__is_confirmed=True,
                          invoice__date__gte=today - timedelta(days=30))
                  .values("variant__model__name")
                  .annotate(qty=Sum("quantity"))
                  .order_by("-qty")[:5])

    labels, revenue, profit = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        p = _period(d, d)
        labels.append(d.strftime("%d/%m"))
        revenue.append(float(p["revenue"]))
        profit.append(float(p["profit"]))

    recent_sales = SaleInvoice.objects.select_related("customer").order_by("-id")[:8]

    # فواتير التوريد اللي لسه ما اتأكدش استلام كميتها
    pending_qs = PurchaseInvoice.objects.filter(is_confirmed=False)
    pending_count = pending_qs.count()
    pending_purchases = []
    for inv in (pending_qs.select_related("supplier")
                .prefetch_related("items__variant__model")
                .order_by("-date", "-id")[:10]):
        items = list(inv.items.all())
        pending_purchases.append({
            "invoice": inv,
            "items": items,
            "qty": sum(i.quantity for i in items),
            "total": sum((i.quantity * i.unit_cost for i in items), 0),
        })

    # المخزون بالنوع والمقاسات
    inventory_overview = []
    for m in (ClothingModel.objects.filter(is_active=True)
              .prefetch_related("variants").order_by("name")):
        sizes = {}
        for v in sorted(m.variants.all(), key=_size_key):
            sizes[v.size] = sizes.get(v.size, 0) + v.quantity
        inventory_overview.append({
            "model": m,
            "total": sum(sizes.values()),
            "sizes": [{"size": k, "qty": q, "low": q <= LOW_STOCK}
                      for k, q in sizes.items()],
        })

    # مديونيات العملاء
    debtors = [c for c in Customer.objects.with_balance() if c.balance > 0]
    debtors.sort(key=lambda c: -c.balance)
    receivable = sum((c.balance for c in debtors), 0)

    # الأوردرات الأونلاين حسب الحالة
    online_counts = dict(OnlineOrder.objects.values_list("status")
                         .annotate(c=Count("id")))
    online_cards = [
        {"key": key, "label": label, "count": online_counts.get(key, 0)}
        for key, label in OnlineOrder.STATUS_CHOICES]

    custody_balance = None
    if request.user.has_perm("trade.view_custodysettlement"):
        custody_balance = custody_summary()["balance"]

    context = {
        **admin.site.each_context(request),
        "title": "لوحة التحكم",
        "custody_balance": custody_balance,
        "inventory_overview": inventory_overview,
        "receivable": receivable,
        "debtors": debtors[:5],
        "debtors_count": len(debtors),
        "online_cards": online_cards,
        "today": today_stats,
        "month": month_stats,
        "month_expenses": month_expenses,
        "net_profit": net_profit,
        "stock_value": stock["value"] or 0,
        "stock_pieces": stock["pieces"] or 0,
        "low_stock": low_stock,
        "low_stock_limit": LOW_STOCK,
        "top_models": top_models,
        "recent_sales": recent_sales,
        "pending_purchases": pending_purchases,
        "pending_count": pending_count,
        "chart": {"labels": labels, "revenue": revenue, "profit": profit},
    }
    return render(request, "trade/dashboard.html", context)
