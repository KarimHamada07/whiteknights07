import hmac
import json

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import ActivityLog
from .notify import config


def _key_ok(request):
    key = config()["FEED_KEY"]
    given = request.headers.get("X-Feed-Key", "")
    return bool(key) and hmac.compare_digest(given, key)


@staff_member_required
@user_passes_test(lambda u: u.is_superuser, login_url="/admin/login/")
def activity(request):
    q = request.GET.get("q", "").strip()
    qs = ActivityLog.objects.all()
    if q:
        qs = qs.filter(text__icontains=q) | ActivityLog.objects.filter(user_name__icontains=q)
    cfg = config()
    if cfg["TOKEN"] and cfg["CHAT_ID"]:
        mode = "إرسال مباشر من السيرفر"
    elif cfg["FEED_KEY"]:
        mode = "عن طريق الناقل (telegram_forwarder.py)"
    else:
        mode = "غير مُعدّ (السجل شغال بس من غير تليجرام)"
    context = {
        **admin.site.each_context(request),
        "title": "سجل النشاط",
        "events": qs.order_by("-id")[:200],
        "pending": ActivityLog.objects.filter(sent=False).count(),
        "mode": mode,
        "q": q,
    }
    return render(request, "trade/activity.html", context)


@csrf_exempt
@require_GET
def activity_feed(request):
    """الناقل بيسحب الأحداث اللي لسه ما اتبعتتش (بمفتاح سري)"""
    if not _key_ok(request):
        return JsonResponse({"error": "forbidden"}, status=403)
    events = ActivityLog.objects.filter(sent=False).order_by("id")[:30]
    return JsonResponse({"events": [{"id": e.id, "message": e.message} for e in events]})


@csrf_exempt
@require_POST
def activity_ack(request):
    """الناقل بيأكد إنه بعت الأحداث دي"""
    if not _key_ok(request):
        return JsonResponse({"error": "forbidden"}, status=403)
    try:
        ids = [int(i) for i in json.loads(request.body).get("ids", [])]
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "bad request"}, status=400)
    updated = ActivityLog.objects.filter(id__in=ids).update(sent=True)
    return JsonResponse({"ok": True, "updated": updated})
