from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum


class ClothingModel(models.Model):
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
    model = models.ForeignKey(ClothingModel, on_delete=models.CASCADE, related_name="variants", verbose_name="الموديل")
    size = models.CharField("المقاس", max_length=20)
    color = models.CharField("اللون", max_length=30, blank=True)
    quantity = models.IntegerField("الكمية بالمخزن", default=0, editable=False)
    avg_cost = models.DecimalField("متوسط التكلفة", max_digits=12, decimal_places=2, default=0, editable=False)
    sale_price = models.DecimalField("سعر البيع", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "مقاس/لون"
        verbose_name_plural = "المقاسات والألوان"
        unique_together = ("model", "size", "color")

    def __str__(self):
        return f"{self.model.name} - {self.size} - {self.color}".strip(" -")


class Supplier(models.Model):
    name = models.CharField("اسم المصنع/المورد", max_length=150)
    phone = models.CharField("الهاتف", max_length=30, blank=True)
    address = models.CharField("العنوان", max_length=250, blank=True)

    class Meta:
        verbose_name = "مصنع/مورد"
        verbose_name_plural = "المصانع والموردين"

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField("اسم العميل", max_length=150)
    phone = models.CharField("الهاتف", max_length=30, blank=True)

    class Meta:
        verbose_name = "عميل"
        verbose_name_plural = "العملاء"

    def __str__(self):
        return self.name


class PurchaseInvoice(models.Model):
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
        return sum((i.quantity * i.unit_cost for i in self.items.all()), Decimal("0"))

    @transaction.atomic
    def confirm(self):
        if self.is_confirmed:
            raise ValidationError("الفاتورة مؤكدة بالفعل")
        if not self.items.exists():
            raise ValidationError("الفاتورة بدون أصناف")
        for item in self.items.select_related("variant"):
            v = Variant.objects.select_for_update().get(pk=item.variant_id)
            new_qty = v.quantity + item.quantity
            v.avg_cost = ((v.quantity * v.avg_cost) + (item.quantity * item.unit_cost)) / new_qty
            v.quantity = new_qty
            v.save()
        self.is_confirmed = True
        self.save()


class PurchaseItem(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, verbose_name="الصنف")
    quantity = models.PositiveIntegerField("الكمية")
    unit_cost = models.DecimalField("سعر الشراء للقطعة", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "بند توريد"
        verbose_name_plural = "بنود التوريد"


class SaleInvoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="العميل")
    date = models.DateField("التاريخ")
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
        gross = sum((i.quantity * i.unit_price for i in self.items.all()), Decimal("0"))
        return gross - self.discount

    @property
    def profit(self):
        gross_profit = sum(((i.unit_price - i.unit_cost) * i.quantity for i in self.items.all()), Decimal("0"))
        return gross_profit - self.discount

    @transaction.atomic
    def confirm(self):
        if self.is_confirmed:
            raise ValidationError("الفاتورة مؤكدة بالفعل")
        if not self.items.exists():
            raise ValidationError("الفاتورة بدون أصناف")
        for item in self.items.select_related("variant"):
            v = Variant.objects.select_for_update().get(pk=item.variant_id)
            if v.quantity < item.quantity:
                raise ValidationError(f"الكمية غير كافية للصنف: {v} (المتاح {v.quantity})")
            item.unit_cost = v.avg_cost
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
    unit_cost = models.DecimalField("التكلفة وقت البيع", max_digits=12, decimal_places=2, default=0, editable=False)

    class Meta:
        verbose_name = "بند بيع"
        verbose_name_plural = "بنود البيع"


class Expense(models.Model):
    title = models.CharField("البند", max_length=150)
    amount = models.DecimalField("المبلغ", max_digits=12, decimal_places=2)
    date = models.DateField("التاريخ")

    class Meta:
        verbose_name = "مصروف"
        verbose_name_plural = "المصروفات"

    def __str__(self):
        return f"{self.title} - {self.amount}"