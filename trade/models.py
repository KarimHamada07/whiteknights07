import os
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import (DecimalField, ExpressionWrapper, F, OuterRef,
                              Subquery, Sum, Value)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .notify import log_event, online_created_text, online_status_text

DEC = DecimalField(max_digits=14, decimal_places=2)
ZERO = Decimal("0")


class ClothingModel(models.Model):
    """موديل ملابس (يمكن إضافة أي عدد من الموديلات)"""
    name = models.CharField("اسم الموديل", max_length=100)
    code = models.CharField("الكود", max_length=30, unique=True)
    description = models.TextField("وصف", blank=True)
    is_active = models.BooleanField("نشط", default=True)

    class Meta:
        verbose_name = "موديل"
        verbose_name_plural = "الموديلات"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Variant(models.Model):
    """مقاس/لون لكل موديل، وعليه المخزون وسعر البيع ومتوسط التكلفة"""
    model = models.ForeignKey(ClothingModel, on_delete=models.CASCADE,
                              related_name="variants", verbose_name="الموديل")
    size = models.CharField("المقاس", max_length=20)
    color = models.CharField("اللون", max_length=30, blank=True)
    quantity = models.IntegerField("الكمية بالمخزن", default=0, editable=False)
    avg_cost = models.DecimalField("متوسط التكلفة", max_digits=12,
                                   decimal_places=2, default=0, editable=False)
    sale_price = models.DecimalField("سعر البيع", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "مقاس/لون"
        verbose_name_plural = "المقاسات والألوان"
        unique_together = ("model", "size", "color")

    def __str__(self):
        return f"{self.model.name} - {self.size} - {self.color}".strip(" -")

    def add_stock(self, qty, unit_cost):
        """إضافة كمية للمخزن مع تحديث متوسط التكلفة (توريد أو مرتجع)"""
        new_qty = self.quantity + qty
        if new_qty > 0:
            self.avg_cost = ((self.quantity * self.avg_cost) +
                             (qty * unit_cost)) / new_qty
        self.quantity = new_qty


class Supplier(models.Model):
    name = models.CharField("اسم المصنع/المورد", max_length=150)
    phone = models.CharField("الهاتف", max_length=30, blank=True)
    address = models.CharField("العنوان", max_length=250, blank=True)

    class Meta:
        verbose_name = "مصنع/مورد"
        verbose_name_plural = "المصانع والموردين"

    def __str__(self):
        return self.name


class CustomerQuerySet(models.QuerySet):
    def with_balance(self):
        """يضيف لكل عميل: credit_total (إجمالي الآجل) و paid_total (المدفوع) و balance (المتبقي)"""
        gross = (SaleItem.objects
                 .filter(invoice__customer=OuterRef("pk"),
                         invoice__is_confirmed=True,
                         invoice__payment_type="credit")
                 .order_by().values("invoice__customer")
                 .annotate(s=Sum(F("quantity") * F("unit_price"), output_field=DEC))
                 .values("s"))
        disc = (SaleInvoice.objects
                .filter(customer=OuterRef("pk"), is_confirmed=True,
                        payment_type="credit")
                .order_by().values("customer")
                .annotate(s=Sum("discount")).values("s"))
        paid = (Payment.objects
                .filter(customer=OuterRef("pk"))
                .order_by().values("customer")
                .annotate(s=Sum("amount")).values("s"))
        return (self
                .annotate(
                    credit_gross=Coalesce(Subquery(gross, output_field=DEC),
                                          Value(ZERO), output_field=DEC),
                    credit_discount=Coalesce(Subquery(disc, output_field=DEC),
                                             Value(ZERO), output_field=DEC),
                    paid_total=Coalesce(Subquery(paid, output_field=DEC),
                                        Value(ZERO), output_field=DEC))
                .annotate(
                    credit_total=ExpressionWrapper(
                        F("credit_gross") - F("credit_discount"), output_field=DEC),
                    balance=ExpressionWrapper(
                        F("credit_gross") - F("credit_discount") - F("paid_total"),
                        output_field=DEC)))


class Customer(models.Model):
    name = models.CharField("اسم العميل", max_length=150)
    phone = models.CharField("الهاتف", max_length=30, blank=True)

    objects = CustomerQuerySet.as_manager()

    class Meta:
        verbose_name = "عميل"
        verbose_name_plural = "العملاء"

    def __str__(self):
        return self.name


class PurchaseInvoice(models.Model):
    """فاتورة توريد من المصنع"""
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="المصنع")
    date = models.DateField("التاريخ")
    notes = models.TextField("ملاحظات", blank=True)
    is_confirmed = models.BooleanField("مؤكدة", default=False, editable=False)

    class Meta:
        verbose_name = "فاتورة توريد"
        verbose_name_plural = "فواتير التوريد"

    def __str__(self):
        return f"توريد #{self.pk} - {self.supplier}"

    @property
    def total(self):
        return sum((i.quantity * i.unit_cost for i in self.items.all()), ZERO)

    @transaction.atomic
    def confirm(self):
        if self.is_confirmed:
            raise ValidationError("الفاتورة مؤكدة بالفعل")
        if not self.items.exists():
            raise ValidationError("الفاتورة بدون أصناف")
        for item in self.items.select_related("variant"):
            v = Variant.objects.select_for_update().get(pk=item.variant_id)
            v.add_stock(item.quantity, item.unit_cost)
            v.save()
        self.is_confirmed = True
        self.save()


class PurchaseItem(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE,
                                related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, verbose_name="الصنف")
    quantity = models.PositiveIntegerField("الكمية")
    unit_cost = models.DecimalField("سعر الشراء للقطعة", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "بند توريد"
        verbose_name_plural = "بنود التوريد"

    def __str__(self):
        return f"{self.variant} × {self.quantity}"


class SaleInvoice(models.Model):
    """فاتورة بيع مباشر (نقدي أو آجل)"""
    PAYMENT_TYPES = [("cash", "نقدي"), ("credit", "آجل")]

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True,
                                 blank=True, verbose_name="العميل")
    date = models.DateField("التاريخ")
    payment_type = models.CharField("طريقة الدفع", max_length=10,
                                    choices=PAYMENT_TYPES, default="cash")
    discount = models.DecimalField("خصم", max_digits=12, decimal_places=2, default=0)
    notes = models.TextField("ملاحظات", blank=True)
    is_confirmed = models.BooleanField("مؤكدة", default=False, editable=False)

    class Meta:
        verbose_name = "فاتورة بيع"
        verbose_name_plural = "فواتير البيع"

    def __str__(self):
        return f"بيع #{self.pk}"

    @property
    def total(self):
        gross = sum((i.quantity * i.unit_price for i in self.items.all()), ZERO)
        return gross - self.discount

    @property
    def profit(self):
        gross_profit = sum(((i.unit_price - i.unit_cost) * i.quantity
                            for i in self.items.all()), ZERO)
        return gross_profit - self.discount

    @property
    def paid_total(self):
        return sum((p.amount for p in self.payments.all()), ZERO)

    @property
    def remaining(self):
        if self.payment_type != "credit":
            return ZERO
        return self.total - self.paid_total

    @transaction.atomic
    def confirm(self):
        if self.is_confirmed:
            raise ValidationError("الفاتورة مؤكدة بالفعل")
        if self.payment_type == "credit" and not self.customer_id:
            raise ValidationError("البيع الآجل لازم يكون له عميل")
        if not self.items.exists():
            raise ValidationError("الفاتورة بدون أصناف")
        for item in self.items.select_related("variant"):
            v = Variant.objects.select_for_update().get(pk=item.variant_id)
            if v.quantity < item.quantity:
                raise ValidationError(f"الكمية غير كافية للصنف: {v} (المتاح {v.quantity})")
            item.unit_cost = v.avg_cost  # تثبيت التكلفة وقت البيع لحساب الربح
            item.save()
            v.quantity -= item.quantity
            v.save()
        self.is_confirmed = True
        self.save()


class SaleItem(models.Model):
    invoice = models.ForeignKey(SaleInvoice, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, verbose_name="الصنف")
    quantity = models.PositiveIntegerField("الكمية")
    unit_price = models.DecimalField("سعر البيع للقطعة", max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField("التكلفة وقت البيع", max_digits=12, decimal_places=2,
                                    default=0, editable=False)

    class Meta:
        verbose_name = "بند بيع"
        verbose_name_plural = "بنود البيع"

    def __str__(self):
        return f"{self.variant} × {self.quantity}"


class Payment(models.Model):
    """دفعة تسديد من عميل (على حساب الآجل)"""
    METHODS = [("cash", "نقدي"), ("transfer", "تحويل"),
               ("wallet", "محفظة إلكترونية"), ("other", "أخرى")]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT,
                                 related_name="payments", verbose_name="العميل")
    invoice = models.ForeignKey(SaleInvoice, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="payments",
                                verbose_name="فاتورة محددة (اختياري)")
    amount = models.DecimalField("المبلغ", max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    date = models.DateField("التاريخ", default=timezone.localdate)
    method = models.CharField("طريقة الدفع", max_length=10, choices=METHODS,
                              default="cash")
    notes = models.CharField("ملاحظات", max_length=200, blank=True)

    class Meta:
        verbose_name = "دفعة تسديد"
        verbose_name_plural = "دفعات التسديد"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.customer} - {self.amount}"

    def clean(self):
        if self.invoice_id and self.customer_id:
            if self.invoice.customer_id != self.customer_id:
                raise ValidationError("الفاتورة دي مش بتاعة نفس العميل")
            if self.invoice.payment_type != "credit":
                raise ValidationError("الفاتورة دي مش آجل")


class OnlineOrder(models.Model):
    """أوردر أونلاين: يتجهز ثم يُشحن ثم يُحصَّل أو يرجع"""
    PREPARED, SHIPPED, COLLECTED, RETURNED = (
        "prepared", "shipped", "collected", "returned")
    STATUS_CHOICES = [
        (PREPARED, "تم التجهيز"),
        (SHIPPED, "تم الشحن"),
        (COLLECTED, "تم التحصيل"),
        (RETURNED, "مرتجع"),
    ]
    TRANSITIONS = {
        PREPARED: [SHIPPED, RETURNED],
        SHIPPED: [COLLECTED, RETURNED],
        COLLECTED: [RETURNED],
        RETURNED: [],
    }

    customer_name = models.CharField("اسم العميل", max_length=150)
    phone = models.CharField("رقم الموبايل", max_length=30)
    address = models.CharField("العنوان", max_length=300, blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    status = models.CharField("الحالة", max_length=12, choices=STATUS_CHOICES,
                              default=PREPARED, db_index=True)
    discount = models.DecimalField("خصم", max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField("مصاريف شحن على العميل", max_digits=12,
                                       decimal_places=2, default=0)
    shipping_cost = models.DecimalField("تكلفة الشحن علينا", max_digits=12,
                                        decimal_places=2, default=0)
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "أوردر أونلاين"
        verbose_name_plural = "الأوردرات الأونلاين"
        ordering = ["-id"]

    def __str__(self):
        return f"أوردر #{self.pk} - {self.customer_name}"

    # ---- حسابات ----
    @property
    def items_total(self):
        return sum((i.quantity * i.unit_price for i in self.items.all()), ZERO)

    @property
    def total_to_collect(self):
        return self.items_total - self.discount + self.shipping_fee

    @property
    def pieces(self):
        return sum((i.quantity for i in self.items.all()), 0)

    @property
    def items_profit(self):
        return sum(((i.unit_price - i.unit_cost) * i.quantity
                    for i in self.items.all()), ZERO)

    @property
    def profit(self):
        """الربح بيتحسب بعد التحصيل فقط. المرتجع بيخسر تكلفة الشحن."""
        if self.status == self.COLLECTED:
            return (self.items_profit - self.discount
                    + self.shipping_fee - self.shipping_cost)
        if self.status == self.RETURNED:
            return -self.shipping_cost
        return ZERO

    @property
    def allowed_next(self):
        labels = dict(self.STATUS_CHOICES)
        return [(s, labels[s]) for s in self.TRANSITIONS[self.status]]

    # ---- عمليات ----
    @classmethod
    @transaction.atomic
    def create_order(cls, *, customer_name, phone, items, address="", notes="",
                     discount=ZERO, shipping_fee=ZERO, shipping_cost=ZERO):
        """ينشئ الأوردر (حالة: تم التجهيز) ويخصم المخزون ويثبت التكلفة"""
        customer_name = (customer_name or "").strip()
        phone = (phone or "").strip()
        if not customer_name or not phone:
            raise ValidationError("اسم العميل ورقم الموبايل مطلوبين")
        if not items:
            raise ValidationError("الأوردر بدون أصناف")
        if min(discount, shipping_fee, shipping_cost) < 0:
            raise ValidationError("الأرقام لازم تكون موجبة")

        order = cls.objects.create(
            customer_name=customer_name, phone=phone, address=address.strip(),
            notes=notes.strip(), discount=discount, shipping_fee=shipping_fee,
            shipping_cost=shipping_cost)
        gross = ZERO
        for it in items:
            qty, price = int(it["qty"]), Decimal(str(it["price"]))
            if qty <= 0 or price < 0:
                raise ValidationError("كمية أو سعر غير صحيح")
            try:
                v = Variant.objects.select_for_update().get(pk=it["id"])
            except Variant.DoesNotExist:
                raise ValidationError("صنف غير موجود")
            if v.quantity < qty:
                raise ValidationError(
                    f"الكمية غير كافية للصنف: {v} (المتاح {v.quantity})")
            OnlineOrderItem.objects.create(
                order=order, variant=v, quantity=qty, unit_price=price,
                unit_cost=v.avg_cost)
            v.quantity -= qty
            v.save()
            gross += qty * price
        if discount > gross:
            raise ValidationError("الخصم أكبر من إجمالي الأوردر")
        log_event(online_created_text(order))
        return order

    @transaction.atomic
    def set_status(self, new_status):
        if new_status not in self.TRANSITIONS.get(self.status, []):
            raise ValidationError("مينفعش تنقل الأوردر للحالة دي")
        if new_status == self.RETURNED:  # المرتجع يرجع للمخزن
            for item in self.items.select_related("variant"):
                v = Variant.objects.select_for_update().get(pk=item.variant_id)
                v.add_stock(item.quantity, item.unit_cost)
                v.save()
        old_status = self.status
        self.status = new_status
        self.save()
        log_event(online_status_text(self, old_status))


class OnlineOrderItem(models.Model):
    order = models.ForeignKey(OnlineOrder, on_delete=models.CASCADE,
                              related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, verbose_name="الصنف")
    quantity = models.PositiveIntegerField("الكمية")
    unit_price = models.DecimalField("سعر البيع للقطعة", max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField("التكلفة وقت البيع", max_digits=12,
                                    decimal_places=2, default=0, editable=False)

    class Meta:
        verbose_name = "بند أوردر"
        verbose_name_plural = "بنود الأوردرات"

    def __str__(self):
        return f"{self.variant} × {self.quantity}"


class Expense(models.Model):
    """مصروفات (إيجار، شحن، مرتبات...) تُخصم من صافي الربح"""
    title = models.CharField("البند", max_length=150)
    amount = models.DecimalField("المبلغ", max_digits=12, decimal_places=2)
    date = models.DateField("التاريخ")

    class Meta:
        verbose_name = "مصروف"
        verbose_name_plural = "المصروفات"

    def __str__(self):
        return f"{self.title} - {self.amount}"


class ActivityLog(models.Model):
    """سجل بكل خطوة في النظام (وبيتبعت لتليجرام)"""
    created_at = models.DateTimeField("الوقت", auto_now_add=True)
    user_name = models.CharField("المستخدم", max_length=150, blank=True)
    text = models.TextField("الحدث")
    sent = models.BooleanField("أُرسل لتليجرام", default=False, db_index=True)

    class Meta:
        verbose_name = "حدث"
        verbose_name_plural = "سجل النشاط"
        ordering = ["-id"]

    def __str__(self):
        return self.text.split("\n")[0]

    @property
    def message(self):
        when = timezone.localtime(self.created_at).strftime("%Y-%m-%d %H:%M:%S")
        who = self.user_name or "—"
        return f"{self.text}\n👤 {who}   🕒 {when}"


def private_storage():
    """مجلد خاص لإثباتات العهدة: مش متاح بروابط مباشرة، بيتقدم بس عن طريق صفحة بتتأكد من الصلاحية"""
    return FileSystemStorage(location=os.path.join(settings.BASE_DIR, "private_media"))


class CustodyDeposit(models.Model):
    """مبلغ بيتضاف على العهدة يدوياً (رصيد موجود قبل النظام أو تمويل)"""
    amount = models.DecimalField("المبلغ", max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    date = models.DateField("التاريخ", default=timezone.localdate)
    note = models.CharField("ملاحظة", max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, editable=False,
                                   verbose_name="سجّلها")

    class Meta:
        verbose_name = "إضافة على العهدة"
        verbose_name_plural = "إضافات على العهدة"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"+{self.amount} ({self.note})"


class CustodySettlement(models.Model):
    """تصفية عهدة: مبلغ اتسلّم لشخص، مع صورة الإثبات (سكرين) واسم المستلم"""
    METHODS = [("cash", "نقدي"), ("transfer", "تحويل بنكي"), ("instapay", "إنستاباي"),
               ("wallet", "محفظة إلكترونية"), ("other", "أخرى")]

    amount = models.DecimalField("المبلغ", max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    received_by = models.CharField("المستلم", max_length=120)
    method = models.CharField("طريقة التسليم", max_length=10, choices=METHODS,
                              default="cash")
    settled_at = models.DateTimeField("وقت التصفية", default=timezone.now)
    notes = models.CharField("ملاحظات", max_length=300, blank=True)
    screenshot = models.FileField("صورة الإثبات (سكرين)", upload_to="custody/",
                                  storage=private_storage, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, editable=False,
                                   verbose_name="سجّلها")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تصفية عهدة"
        verbose_name_plural = "تصفيات العهدة"
        ordering = ["-settled_at", "-id"]

    def __str__(self):
        return f"تصفية {self.amount} إلى {self.received_by}"

    @property
    def has_proof(self):
        return bool(self.screenshot)
