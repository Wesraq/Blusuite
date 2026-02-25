from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnouncementReadViewSet,
    AnnouncementViewSet,
    ChatGroupViewSet,
    DirectMessageViewSet,
    GroupMessageReadViewSet,
    GroupMessageViewSet,
)

router = DefaultRouter()
router.register(r'groups', ChatGroupViewSet, basename='communication-groups')
router.register(r'group-messages', GroupMessageViewSet, basename='communication-group-messages')
router.register(r'group-reads', GroupMessageReadViewSet, basename='communication-group-reads')
router.register(r'direct-messages', DirectMessageViewSet, basename='communication-direct-messages')
router.register(r'announcements', AnnouncementViewSet, basename='communication-announcements')
router.register(r'announcement-reads', AnnouncementReadViewSet, basename='communication-announcement-reads')

urlpatterns = [
    path('', include(router.urls)),
]
