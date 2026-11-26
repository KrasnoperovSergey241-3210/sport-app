from datetime import date

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


class RegistrationDetailsSerializer(serializers.Serializer):
    birth_date = serializers.DateField()
    consent = serializers.BooleanField()

    def validate_consent(self, v):
        if v is not True:
            raise serializers.ValidationError("Без согласия на обработку персональных данных работа с приложением невозможна")
        return v

    def validate_birth_date(self, v):
        if v > date.today() or v.year < 1900:
            raise serializers.ValidationError("Некорректная дата рождения")
        return v


class RegisterStartSerializer(RegistrationDetailsSerializer):
    contact = serializers.CharField(max_length=254)


class RegisterSerializer(RegistrationDetailsSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, validators=[validate_password])


class RegisterVerifySerializer(serializers.Serializer):
    contact = serializers.CharField(max_length=254)
    code = serializers.CharField(max_length=10)
    password = serializers.CharField(write_only=True, max_length=128, validators=[validate_password])


class LoginSerializer(serializers.Serializer):
    contact = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=128)


class ContactSerializer(serializers.Serializer):
    contact = serializers.CharField(max_length=254)


class OtpVerifySerializer(serializers.Serializer):
    contact = serializers.CharField(max_length=254)
    code = serializers.CharField(max_length=10)


class ResetConfirmSerializer(serializers.Serializer):
    contact = serializers.CharField(max_length=254)
    code = serializers.CharField(max_length=10)
    new_password = serializers.CharField(max_length=128)


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=128)
