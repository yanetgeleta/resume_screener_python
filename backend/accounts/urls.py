from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.views import CompanyCreateView, CompanyTokenRefreshView, LogoutView

app_name = "accounts"

urlpatterns = [
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", CompanyTokenRefreshView.as_view(), name="token_refresh"),
    path("register/", CompanyCreateView.as_view(), name="register_company"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
