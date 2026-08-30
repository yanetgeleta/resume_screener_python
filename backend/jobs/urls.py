from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApplicationViewSet, JobViewSet, ResumeViewSet

router = DefaultRouter()
router.register(r"jobs", JobViewSet, basename="job")
router.register(r"applications", ApplicationViewSet, basename="application")
router.register(r"resumes", ResumeViewSet, basename="resume")

urlpatterns = [path("", include(router.urls))]
