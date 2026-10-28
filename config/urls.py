from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from trade.activity_views import activity, activity_ack, activity_feed
from trade.custody_views import (custody, custody_deposit, custody_detail,
                                 custody_receipt, custody_screenshot, custody_settle)
from trade.customer_views import (customer_add, customer_detail, customer_pay,
                                  customers)
from trade.online_views import (online_create, online_detail, online_list,
                                online_new, online_status)
from trade.pos_views import pos, pos_checkout, sale_print
from trade.stock_views import inventory, inventory_detail, purchase_confirm
from trade.views import dashboard

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("dashboard/", dashboard, name="dashboard"),
    path("pos/", pos, name="pos"),
    path("pos/checkout/", pos_checkout, name="pos_checkout"),
    path("invoice/<int:pk>/", sale_print, name="sale_print"),
    path("inventory/", inventory, name="inventory"),
    path("inventory/<int:pk>/", inventory_detail, name="inventory_detail"),
    path("purchase/<int:pk>/confirm/", purchase_confirm, name="purchase_confirm"),
    path("activity/", activity, name="activity"),
    path("activity/feed/", activity_feed, name="activity_feed"),
    path("activity/ack/", activity_ack, name="activity_ack"),
    path("custody/", custody, name="custody"),
    path("custody/settle/", custody_settle, name="custody_settle"),
    path("custody/deposit/", custody_deposit, name="custody_deposit"),
    path("custody/<int:pk>/", custody_detail, name="custody_detail"),
    path("custody/<int:pk>/screenshot/", custody_screenshot, name="custody_screenshot"),
    path("custody/<int:pk>/receipt/", custody_receipt, name="custody_receipt"),
    path("customers/", customers, name="customers"),
    path("customers/add/", customer_add, name="customer_add"),
    path("customers/<int:pk>/", customer_detail, name="customer_detail"),
    path("customers/<int:pk>/pay/", customer_pay, name="customer_pay"),
    path("online/", online_list, name="online_list"),
    path("online/new/", online_new, name="online_new"),
    path("online/create/", online_create, name="online_create"),
    path("online/<int:pk>/", online_detail, name="online_detail"),
    path("online/<int:pk>/status/", online_status, name="online_status"),
    # زر Dashboard في القائمة يفتح لوحة التحكم الجديدة
    path("admin/", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("admin/", admin.site.urls),
]


