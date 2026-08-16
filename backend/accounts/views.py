import time

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import CompanyRegisterSerializer, CompanyTokenRefreshSerializer

# Create your views here.
Company = get_user_model()


class CompanyCreateView(generics.CreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyRegisterSerializer


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token_str = request.data.get("refresh")

        if not refresh_token_str:
            return Response(
                {"error": "Refresh token is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token_str)
            jti = token["jti"]
            exp = token["exp"]

            current_time = int(time.time())
            ttl = exp - current_time

            if ttl > 0:
                cache.set(f"blocklist_jti_{jti}", "revoked", timeout=ttl)

            return Response(
                {"detail": "Successfully logged out."}, status=status.HTTP_200_OK
            )
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CompanyTokenRefreshView(TokenRefreshView):
    serializer_class = CompanyTokenRefreshSerializer
