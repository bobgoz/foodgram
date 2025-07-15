from django.contrib.auth import get_user_model
from rest_framework import serializers

from foodgram.models import Recipe

User = get_user_model()


class RecipePrimaryKeyMixin(serializers.Serializer):
    """
    Миксин с полем Recipe как PrimaryKeyRelatedField
    с сообщением об ошибке при несуществующем id рецепта.
    """
    recipe = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(),
        error_messages={
            'does_not_exist': 'Рецепта с таким id не существует.',
        }
    )


class AuthorPrimaryKeyMixin(serializers.Serializer):
    """
    Миксин с полем Author как PrimaryKeyRelatedField
    с сообщением об ошибке при несуществующем id автора.
    """
    author = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        error_messages={
            'does_not_exist': 'Пользователя с таким id не существует.',
        }
    )
