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


class BaseDeleteMixin(serializers.Serializer):
    """Базовый миксин для удаления записей о корзине покупок и избранных."""

    relation_model = None
    relation_field = None
    not_found_message = None

    def validate(self, attrs):
        """Проверка на существование связи перед удалением."""
        user = self.context['request'].user
        obj = attrs[self.relation_field]

        relation_exists = self.relation_model.objects.filter(
            user=user,
            **{self.relation_field: obj}
        ).exists()

        if not relation_exists:
            serializers.ValidationError(
                self.not_found_message,
                code='not found',
            )
        return attrs

    def delete(self):
        """Удаление связи."""
        self.relation_model.objects.filter(
            user=self.context['request'].user,
            **{self.relation_field: self.validated_data[self.relation_field]}
        ).delete()


class BaseCreateMixin(serializers.Serializer):
    """Базовый миксин для создания записей о корзине покупок и избранных."""

    relation_model = None
    message = None

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault(),
    )

    def __init_subclass__(cls, **kwargs):
        """Динамически создаем Meta класс для дочерних сериализаторов."""

        super().__init_subclass__(**kwargs)

        if cls.relation_model is None:
            raise NotImplementedError(
                "Дочерний класс должен переопределить `relation_model`!"
            )

        cls.Meta = type(
            'Meta',
            (),
            {
                'model': cls.relation_model,
                'fields': ('user', 'recipe'),
                'validators': [
                    serializers.UniqueTogetherValidator(
                        queryset=cls.relation_model.objects.all(),
                        fields=('user', 'recipe'),
                        message=cls.message,
                    )
                ],
            }
        )

    def to_representation(self, instance):
        """Возвращает ответ с нужными полями."""
        # Во избежание циклического импорта импортируем модуль здесь.
        from .serializers import RecipeShortSerializer

        return RecipeShortSerializer(
            instance.recipe,
            context=self.context,
        ).data
