from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from trade.pos_views import pos, pos_checkout, sale_print
from trade.views import dashboard

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("dashboard/", dashboard, name="dashboard"),
    path("pos/", pos, name="pos"),
    path("pos/checkout/", pos_checkout, name="pos_checkout"),
    path("invoice/<int:pk>/", sale_print, name="sale_print"),
    # زر Dashboard في القائمة يفتح لوحة التحكم الجديدة
    path("admin/", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("admin/", admin.site.urls),
]