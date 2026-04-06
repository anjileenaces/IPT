from clinic.models import Notification


def notification_badge(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, read=False).count()
        return {"unread_notification_count": count}
    return {"unread_notification_count": 0}
