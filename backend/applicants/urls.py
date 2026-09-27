from django.urls import path

from applicants.views import (
    ApplicantApplicationListView,
    ApplicantLoginView,
    ApplicantProfileView,
    ApplicantResumeListView,
    ApplicantSignupView,
)

app_name = "applicants"

urlpatterns = [
    path("signup/", ApplicantSignupView.as_view(), name="signup"),
    path("login/", ApplicantLoginView.as_view(), name="login"),
    path("me/", ApplicantProfileView.as_view(), name="me"),
    path("me/resumes/", ApplicantResumeListView.as_view(), name="me-resumes"),
    path("me/applications/", ApplicantApplicationListView.as_view(), name="me-applications"),
]
