import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, F, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (CustodyDeposit, CustodySettlement, Expense, OnlineOrder,
                     Payment, SaleInvoice, SaleItem)
from .notify import fmt, log_event

ZERO = Decimal("0")
DEC = DecimalField(max_digits=14, decimal_places=2)
MAX_UPLOAD = 8 * 1024 * 1024
# الأوردر الأونلاين المحصّل: المبلغ اللي بيوصل فعلاً = المطلوب تحصيله - تكلفة الشحن
# (شركات الشحن غالباً بتخصم أجرتها من التحصيل). غيّرها لـ False لو بتدفع الشحن بشكل منفصل.
ONLINE_NET_OF_SHIPPING_COST = True

IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}


def custody_summary():
    """المبالغ الموجودة (العهدة) = المقبوضات + الإضافات اليدوية - المصروفات - اللي اتصفّى"""
    gross = SaleItem.objects.filter(
        invoice__is_confirmed=True, invoice__payment_type="cash"
    ).aggregate(g=Sum(F("quantity") * F("unit_price"), output_field=DEC))["g"] or ZERO
    discount = SaleInvoice.objects.filter(
        is_confirmed=True, payment_type="cash"
    ).aggregate(d=Sum("discount"))["d"] or ZERO
    cash_sales = gross - discount

    online = ZERO
    for o in OnlineOrder.objects.filter(status=OnlineOrder.COLLECTED).prefetch_related("items"):
        online += o.total_to_collect
        if ONLINE_NET_OF_SHIPPING_COST:
            online -= o.shipping_cost

    payments = Payment.objects.aggregate(s=Sum("amount"))["s"] or ZERO
    deposits = CustodyDeposit.objects.aggregate(s=Sum("amount"))["s"] or ZERO
    expenses = Expense.objects.aggregate(s=Sum("amount"))["s"] or ZERO
    settled = CustodySettlement.objects.aggregate(s=Sum("amount"))["s"] or ZERO

    total_in = cash_sales + online + payments + deposits
    return {
        "cash_sales": cash_sales, "online": online, "payments": payments,
        "deposits": deposits, "total_in": total_in,
        "expenses": expenses, "settled": settled,
        "balance": total_in - expenses - settled,
    }


def _need(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied


def _image_kind(head):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def _amount(raw):
    try:
        return Decimal((raw or "").strip().replace(",", "") or "0")
    except InvalidOperation:
        return ZERO


@staff_member_required
def custody(request):
    _need(request, "trade.view_custodysettlement")
    q = request.GET.get("q", "").strip()
    noproof = request.GET.get("noproof") == "1"

    qs = CustodySettlement.objects.select_related("created_by")
    if q:
        qs = qs.filter(Q(received_by__icontains=q) | Q(notes__icontains=q))
    if noproof:
        qs = qs.filter(screenshot="")
    page = Paginator(qs, 15).get_page(request.GET.get("page"))

    context = {
        **admin.site.each_context(request),
        "title": "العهدة",
        "s": custody_summary(),
        "page": page,
        "q": q,
        "noproof": noproof,
        "by_receiver": (CustodySettlement.objects.values("received_by")
                        .annotate(total=Sum("amount"), n=Count("id")).order_by("-total")),
        "receivers": [r["received_by"] for r in (
            CustodySettlement.objects.values("received_by")
            .annotate(n=Count("id")).order_by("-n")[:30])],
        "methods": CustodySettlement.METHODS,
        "now": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "today": date.today().isoformat(),
        "deposits": CustodyDeposit.objects.all()[:5],
        "can_add": request.user.has_perm("trade.add_custodysettlement"),
        "can_deposit": request.user.has_perm("trade.add_custodydeposit"),
    }
    return render(request, "trade/custody.html", context)


@staff_member_required
@require_POST
def custody_settle(request):
    _need(request, "trade.add_custodysettlement")
    amount = _amount(request.POST.get("amount"))
    receiver = request.POST.get("received_by", "").strip()[:120]
    method = request.POST.get("method", "cash")
    if method not in dict(CustodySettlement.METHODS):
        method = "cash"

    if amount <= 0:
        messages.error(request, "اكتب مبلغ صحيح أكبر من صفر")
        return redirect("custody")
    if not receiver:
        messages.error(request, "اكتب اسم المستلم")
        return redirect("custody")

    try:
        when = timezone.make_aware(datetime.fromisoformat(request.POST.get("settled_at", "")))
    except (ValueError, TypeError):
        when = timezone.now()

    upload = request.FILES.get("screenshot")
    data = kind = None
    if upload:
        if upload.size > MAX_UPLOAD:
            messages.error(request, "الصورة أكبر من 8 ميجا")
            return redirect("custody")
        data = upload.read()
        kind = _image_kind(data[:16])
        if kind is None:
            messages.error(request, "الملف لازم يكون صورة (PNG أو JPG أو WEBP)")
            return redirect("custody")

    balance_before = custody_summary()["balance"]
    st = CustodySettlement(
        amount=amount, received_by=receiver, method=method, settled_at=when,
        notes=request.POST.get("notes", "").strip()[:300], created_by=request.user)
    if data:
        st.screenshot.save(f"{uuid.uuid4().hex}.{kind}", ContentFile(data), save=False)
    st.save()

    balance = balance_before - amount
    proof = "📎 بإثبات" if st.has_proof else "بدون إثبات"
    log_event(f"🏦 تصفية عهدة {fmt(amount)} — المستلم: {receiver} — "
              f"{st.get_method_display()} — {proof}\nالمتبقي في العهدة: {fmt(balance)}")

    messages.success(request, f"تم تسجيل تصفية {fmt(amount)} للمستلم {receiver}")
    if amount > balance_before:
        messages.warning(
            request, f"المبلغ أكبر من رصيد العهدة المسجل ({fmt(balance_before)}). "
                     "لو في مبلغ موجود قبل النظام، سجّله من 'إضافة على العهدة'.")
    return redirect("custody_detail", pk=st.pk)


@staff_member_required
@require_POST
def custody_deposit(request):
    _need(request, "trade.add_custodydeposit")
    amount = _amount(request.POST.get("amount"))
    if amount <= 0:
        messages.error(request, "اكتب مبلغ صحيح أكبر من صفر")
        return redirect("custody")
    try:
        when = date.fromisoformat(request.POST.get("date", ""))
    except ValueError:
        when = date.today()
    note = request.POST.get("note", "").strip()[:200]
    CustodyDeposit.objects.create(amount=amount, date=when, note=note,
                                  created_by=request.user)
    log_event(f"➕ إضافة على العهدة {fmt(amount)}" + (f" — {note}" if note else ""))
    messages.success(request, f"اتضاف {fmt(amount)} على العهدة")
    return redirect("custody")


@staff_member_required
def custody_detail(request, pk):
    _need(request, "trade.view_custodysettlement")
    st = get_object_or_404(CustodySettlement.objects.select_related("created_by"), pk=pk)
    return render(request, "trade/custody_detail.html", {
        **admin.site.each_context(request), "title": f"تصفية عهدة #{st.pk}", "st": st})


@staff_member_required
def custody_screenshot(request, pk):
    """الصورة بتتقدم من هنا بس (مع فحص الصلاحية). مفيش رابط مباشر ليها."""
    _need(request, "trade.view_custodysettlement")
    st = get_object_or_404(CustodySettlement, pk=pk)
    if not st.screenshot:
        raise Http404
    ext = st.screenshot.name.rsplit(".", 1)[-1].lower()
    try:
        f = st.screenshot.open("rb")
    except FileNotFoundError:
        raise Http404
    resp = FileResponse(f, content_type=IMAGE_TYPES.get(ext, "application/octet-stream"))
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Cache-Control"] = "private, max-age=3600"
    return resp


@staff_member_required
def custody_receipt(request, pk):
    _need(request, "trade.view_custodysettlement")
    st = get_object_or_404(CustodySettlement.objects.select_related("created_by"), pk=pk)
    return render(request, "trade/custody_receipt.html",
                  {"st": st, "shop_name": "Ultras White Knights"})
