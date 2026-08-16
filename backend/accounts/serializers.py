from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

Company = get_user_model()


class CompanyRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    class Meta:
        model = Company
        fields = ("id", "email", "company_name", "password")

    def create(self, validated_data):
        return Company.objects.create_user(**validated_data)


class CompanyTokenRefreshSerializer(TokenRefreshSerializer):
    """Checks whether a token has been blacklisted and raises an error or returns token"""

    def validate(self, attrs):
        data = super().validate(attrs)

        refresh_token_string = attrs["refresh"]
        token_object = RefreshToken(refresh_token_string)
        jti = token_object.payload.get("jti")

        if jti and cache.get(f"blocklist_jti_{jti}"):
            raise InvalidToken("This refresh token has been revoked or blocked.")
        return data
