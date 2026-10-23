from datetime import timedelta
import requests

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import DecimalField, F, Sum
from django.shortcuts import render
from django.utils import timezone

from .models import Expense, SaleInvoice, SaleItem, Variant

LOW_STOCK = 5  # أي صنف كميته أقل من أو تساوي الرقم ده يظهر في التنبيهات
DEC = DecimalField(max_digits=14, decimal_places=2)


def send_telegram_notification(message):
    BOT_TOKEN = "8881158933:AAGJLD3xwtcQuW62agk67GAg7Sul5IAZdJs"
    CHAT_ID = "-1004400889862"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        requests.post(url, data=payload, timeout=3)
    except Exception as e:
        print(f"Telegram Log Exception: {e}")


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
    return {
        "revenue": revenue,
        "profit": profit,
        "pieces": agg["pcs"] or 0,
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

    context = {
        **admin.site.each_context(request),
        "title": "لوحة التحكم",
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
        "chart": {"labels": labels, "revenue": revenue, "profit": profit},
    }
    return render(request, "trade/dashboard.html", context)