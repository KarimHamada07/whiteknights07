from django.apps import AppConfig


class TradeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trade'
    verbose_name = 'إدارة المحل'

    def ready(self):
        from . import signals  # noqa: F401  (تسجيل أحداث النظام)
