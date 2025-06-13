from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.validators import RegexValidator
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from rest_framework import serializers
from rest_framework import status
from rest_framework.validators import UniqueValidator
from rest_framework.response import Response

from foodgram.models import Recipe, Tag, Ingredient
from .validators import validate_forbidden_usernames
from .utils import send_confirm_mail

User = get_user_model()

class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Рецепты. """

    class Meta:
        fields = '__all__'
        model = Recipe


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Тэг"""

    class Meta:
        fields = '__all__'
        model = Tag


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Ингредиент"""

    class Meta:
        fields = '__all__'
        model = Ingredient


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для модели пользователя (User)"""

    class Meta:
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )
        model = User


class UserRegistrationsSerializer(serializers.Serializer):
    """Сериализатор для регистрации пользователя."""

    username = serializers.CharField(
        max_length=150,
        required=True,
        validators=[
            UnicodeUsernameValidator(),
            RegexValidator(
                regex='^[\w.@+-]+$',
                message=(
                    'Имя пользователя содержит недопустимые символы'
                )
            ),
            validate_forbidden_usernames,
            UniqueValidator(queryset=User.objects.all(),
                            message='Этот username уже используется'),
        ],
    )
    first_name = serializers.CharField(
        max_length=150,
        required=True,)
    last_name = serializers.CharField(
        max_length=150,
        required=True,)
    email = serializers.EmailField(
        max_length=254,
        required=True,
        validators=[
            UniqueValidator(queryset=User.objects.all(),
                            message='Этот email уже используется.')
        ]
    )
    password = serializers.CharField(
        write_only=True,  # Пароль никогда не возвращается в ответах API
        required=True,
        min_length=8,
        max_length=128,
        trim_whitespace=False,  # Запрет на обрезку пробелов
        error_messages={
            'min_length': 'Пароль должен содержать минимум 8 символов.',
            'blank': 'Пароль не может быть пустым.'
        }
    )

    def create(self, validated_data):
        user, _ = User.objects.get_or_create(**validated_data)
        confirmation_code = default_token_generator.make_token(user)
        send_confirm_mail(user, confirmation_code)
        return user


class TokenSerializer(serializers.Serializer):
    """
    Сериализатор для получения токена.

    Используется для валидации данных (username и confirmation_code)
    при запросе токена.

    Атрибуты:
        username (CharField):  Имя пользователя.
        confirmation_code (CharField): Код подтверждения.
    """
    confirmation_code = serializers.CharField(required=True)
    username = serializers.CharField(
        max_length=150,
        required=True,
    )

    def validate(self, data):
        """Проверка валидности кода подтверждения."""
        user = get_object_or_404(User, username=data['username'])
        if not default_token_generator.check_token(
            user,
            data['confirmation_code'],
        ):
            raise serializers.ValidationError(
                {'confirmation_code': 'Неверный код подтверждения'}
            )
        return data

    def create(self, validated_data):
        """Активация пользователя и возвращение токена"""

        username = validated_data['username']
        user = get_object_or_404(User, username=username)
        user.is_active = True
        user.save()
        token = AccessToken.for_user(user)
        refresh_token = RefreshToken.for_user(user)
        return {
            'username': user.username,
            'token': str(token),
            'refresh_token': str(refresh_token),
        }
