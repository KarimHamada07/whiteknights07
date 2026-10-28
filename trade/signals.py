from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import (Customer, Expense, Payment, PurchaseInvoice, SaleInvoice,
                     Variant)
from .notify import (LOW_STOCK, log_event, payment_text, purchase_text,
                     sale_text)


def _was_confirmed(model, instance):
    return bool(instance.pk and model.objects.filter(
        pk=instance.pk, is_confirmed=True).exists())


# ---- فواتير البيع والتوريد: الحدث بيتسجل لحظة التأكيد ----
@receiver(pre_save, sender=SaleInvoice)
def _sale_before(sender, instance, **kw):
    instance._was_confirmed = _was_confirmed(sender, instance)


@receiver(post_save, sender=SaleInvoice)
def _sale_after(sender, instance, **kw):
    if instance.is_confirmed and not getattr(instance, "_was_confirmed", False):
        log_event(sale_text(instance))


@receiver(pre_save, sender=PurchaseInvoice)
def _purchase_before(sender, instance, **kw):
    instance._was_confirmed = _was_confirmed(sender, instance)


@receiver(post_save, sender=PurchaseInvoice)
def _purchase_after(sender, instance, **kw):
    if instance.is_confirmed and not getattr(instance, "_was_confirmed", False):
        log_event(purchase_text(instance))


# ---- دفعات وعملاء ومصروفات ----
@receiver(post_save, sender=Payment)
def _payment(sender, instance, created, **kw):
    if created:
        log_event(payment_text(instance))


@receiver(post_save, sender=Customer)
def _customer(sender, instance, created, **kw):
    if created:
        phone = f" — {instance.phone}" if instance.phone else ""
        log_event(f"👤 عميل جديد: {instance.name}{phone}")


@receiver(post_save, sender=Expense)
def _expense(sender, instance, created, **kw):
    if created:
        log_event(f"💸 مصروف: {instance.title} — {instance.amount:,.2f}")


# ---- تنبيه المخزون ----
@receiver(pre_save, sender=Variant)
def _variant_before(sender, instance, **kw):
    instance._old_qty = (
        sender.objects.filter(pk=instance.pk).values_list("quantity", flat=True).first()
        if instance.pk else None)


@receiver(post_save, sender=Variant)
def _variant_after(sender, instance, created, **kw):
    old = getattr(instance, "_old_qty", None)
    if created or old is None:
        return
    if instance.quantity <= 0 < old:
        log_event(f"⛔ نفد من المخزن: {instance}")
    elif instance.quantity <= LOW_STOCK < old:
        log_event(f"⚠️ مخزون منخفض: {instance} — الكمية {instance.quantity}")


# ---- الدخول وإجراءات لوحة الإدارة ----
@receiver(user_logged_in)
def _login(sender, request, user, **kw):
    log_event(f"🔐 تسجيل دخول: {user.get_username()}", user=user)


@receiver(user_login_failed)
def _login_failed(sender, credentials, request=None, **kw):
    ip = ""
    if request is not None:
        ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
              or request.META.get("REMOTE_ADDR", ""))
    log_event(f"🚫 محاولة دخول فاشلة باسم: {credentials.get('username', '')} {ip}".strip())


@receiver(post_save, sender=LogEntry)
def _admin_action(sender, instance, created, **kw):
    if not created:
        return
    verb = {ADDITION: "➕ إضافة", CHANGE: "✏️ تعديل",
            DELETION: "🗑 حذف"}.get(instance.action_flag, "⚙️ إجراء")
    log_event(f"{verb} من لوحة الإدارة\n{instance.content_type}: {instance.object_repr}",
              user=instance.user)
