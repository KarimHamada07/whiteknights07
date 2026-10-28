from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Customer, Payment, SaleInvoice

ZERO = Decimal("0")


@staff_member_required
def customers(request):
    q = request.GET.get("q", "").strip()
    only_debt = request.GET.get("debt") == "1"

    all_customers = list(Customer.objects.with_balance().order_by("name"))
    receivable = sum((c.balance for c in all_customers if c.balance > 0), ZERO)
    debtors = [c for c in all_customers if c.balance > 0]

    rows = all_customers
    if q:
        ql = q.lower()
        rows = [c for c in rows if ql in c.name.lower() or q in (c.phone or "")]
    if only_debt:
        rows = [c for c in rows if c.balance > 0]
    rows.sort(key=lambda c: (-c.balance, c.name))

    context = {
        **admin.site.each_context(request),
        "title": "العملاء والآجل",
        "rows": rows,
        "q": q,
        "only_debt": only_debt,
        "receivable": receivable,
        "debtors_count": len(debtors),
        "customers_count": len(all_customers),
    }
    return render(request, "trade/customers.html", context)


@staff_member_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.with_balance(), pk=pk)

    invoices = (SaleInvoice.objects
                .filter(customer=customer, is_confirmed=True, payment_type="credit")
                .prefetch_related("items", "payments")
                .order_by("-date", "-id"))
    invoice_rows = []
    for inv in invoices:
        total = inv.total
        paid = sum((p.amount for p in inv.payments.all()), ZERO)
        invoice_rows.append({
            "invoice": inv, "total": total, "paid": paid,
            "remaining": total - paid,
        })

    payments = customer.payments.select_related("invoice").order_by("-date", "-id")

    context = {
        **admin.site.each_context(request),
        "title": customer.name,
        "customer": customer,
        "invoice_rows": invoice_rows,
        "open_invoices": [r for r in invoice_rows if r["remaining"] > 0],
        "payments": payments,
        "today": date.today().isoformat(),
        "methods": Payment.METHODS,
    }
    return render(request, "trade/customer_detail.html", context)


@staff_member_required
@require_POST
def customer_add(request):
    if not request.user.has_perm("trade.add_customer"):
        raise PermissionDenied
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    if not name:
        messages.error(request, "اسم العميل مطلوب")
        return redirect("customers")
    customer = Customer.objects.create(name=name, phone=phone)
    messages.success(request, f"تمت إضافة العميل {customer.name}")
    return redirect("customer_detail", pk=customer.pk)


@staff_member_required
@require_POST
def customer_pay(request, pk):
    if not request.user.has_perm("trade.add_payment"):
        raise PermissionDenied
    customer = get_object_or_404(Customer.objects.with_balance(), pk=pk)

    try:
        amount = Decimal(request.POST.get("amount", "0").strip() or "0")
    except InvalidOperation:
        amount = ZERO
    if amount <= 0:
        messages.error(request, "اكتب مبلغ صحيح أكبر من صفر")
        return redirect("customer_detail", pk=pk)
    if amount > customer.balance:
        messages.error(
            request, f"المبلغ أكبر من المتبقي على العميل ({customer.balance:.2f})")
        return redirect("customer_detail", pk=pk)

    invoice = None
    invoice_id = request.POST.get("invoice")
    if invoice_id:
        invoice = SaleInvoice.objects.filter(
            pk=invoice_id, customer=customer, payment_type="credit",
            is_confirmed=True).first()
        if invoice is None:
            messages.error(request, "الفاتورة المختارة غير صحيحة")
            return redirect("customer_detail", pk=pk)

    method = request.POST.get("method", "cash")
    if method not in dict(Payment.METHODS):
        method = "cash"
    try:
        pay_date = date.fromisoformat(request.POST.get("date", ""))
    except ValueError:
        pay_date = date.today()

    Payment.objects.create(
        customer=customer, invoice=invoice, amount=amount, date=pay_date,
        method=method, notes=request.POST.get("notes", "").strip()[:200])
    messages.success(request, f"تم تسجيل دفعة {amount:.2f} من {customer.name}")
    return redirect("customer_detail", pk=pk)
