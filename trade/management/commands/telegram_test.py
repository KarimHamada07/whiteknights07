from django.core.management.base import BaseCommand

from trade.models import ActivityLog
from trade.notify import config, log_event, send_telegram


class Command(BaseCommand):
    help = "يسجل حدث تجربة ويفحص إرسال تليجرام"

    def handle(self, *args, **options):
        cfg = config()
        log_event("🧪 رسالة تجربة من النظام")
        pending = ActivityLog.objects.filter(sent=False).count()

        if cfg["TOKEN"] and cfg["CHAT_ID"]:
            self.stdout.write("وضع الإرسال المباشر: بجرّب الاتصال بتليجرام...")
            ok, detail = send_telegram(cfg["TOKEN"], cfg["CHAT_ID"], "🧪 فحص الاتصال")
            if ok:
                self.stdout.write(self.style.SUCCESS("تمام: تليجرام استقبل الرسالة."))
            else:
                self.stdout.write(self.style.ERROR(f"فشل الإرسال: {detail}"))
                self.stdout.write("لو الخطأ فيه 403 أو ProxyError أو Tunnel، يبقى الحساب المجاني "
                                  "بيمنع الاتصال بتليجرام. استخدم الناقل (احذف TOKEN و CHAT_ID "
                                  "من الملف على السيرفر واترك FEED_KEY بس).")
        elif cfg["FEED_KEY"]:
            self.stdout.write(self.style.SUCCESS(
                f"وضع الناقل: الحدث اتسجل وبيستنى الناقل. بانتظار الإرسال: {pending}"))
        else:
            self.stdout.write(self.style.WARNING(
                "مفيش إعداد تليجرام على السيرفر (الملف ~/.telegram_bot). السجل شغال في الموقع بس."))
