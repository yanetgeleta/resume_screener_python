from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApplicationViewSet,
    ChatSessionViewSet,
    JobViewSet,
    ResumeViewSet,
    chat_stream_view,
)

router = DefaultRouter()
router.register(r"jobs", JobViewSet, basename="job")
router.register(r"applications", ApplicationViewSet, basename="application")
router.register(r"resumes", ResumeViewSet, basename="resume")
router.register(r"sessions", ChatSessionViewSet, basename="session")
router.register(r"chat-sessions", ChatSessionViewSet, basename="chat-session")

urlpatterns = [
    path(
        "sessions/<int:session_id>/stream/",
        chat_stream_view,
        name="chat-session-stream",
    ),
    path(
        "chat/sessions/<int:session_id>/stream/",
        chat_stream_view,
        name="chat-stream",
    ),
    path("", include(router.urls)),
]

