from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from djoser.serializers import UserSerializer
from drf_extra_fields.fields import Base64ImageField

from foodgram.models import (
    Recipe,
    Tag,
    Ingredient,
    RecipeIngredient,
    Favorite,
)
from .constants import (
    AMOUNT_MIN_VALUE,
    AMOUNT_MAX_VALUE,
    COOKING_TIME_MIN_VALUE,
    COOKING_TIME_MAX_VALUE,
)
from .fields import TagPrimaryKeyField

User = get_user_model()


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Тэг"""

    class Meta:
        fields = '__all__'
        model = Tag


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Ингредиент"""

    measurement_unit = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        fields = '__all__'
        model = Ingredient


class UserSerializer(UserSerializer):
    """Сериализатор, наследуемый от сериализатора Djoser."""

    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )

    def get_is_subscribed(self, obj):
        """Возвращает булево значение в зависимости от наличия подписки."""
        request = self.context['request']
        if not request.user.is_authenticated:
            return False
        return obj.following.filter(user=request.user).exists()


# class IngredientShowSerializer(serializers.ModelSerializer):
#     """Сериализатор, возвращающий информацию об ингредиентах."""

#     class Meta:
#         model = Ingredient
#         fields = ('id', 'name', 'measurement_unit',)


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Рецепты. """

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientSerializer(many=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField(required=True)

    class Meta:
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )
        model = Recipe

    def get_is_favorited(self, obj):
        """
        Возвращает булево значение в зависимости
        от наличия избранных рецептов.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.favorites.filter(user=request.user).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        """
        Возвращает булево значение в зависимости
        от наличия корзины покупок.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.in_shopping_carts.filter(user=request.user).exists()
        return False


class RecipeIngredientInputSerializer(serializers.Serializer):
    """
    Сериализатор, предназначенный для
    сериализатора RecipeCreateUpdateSerializer.
    """

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
    )
    amount = serializers.IntegerField(
        min_value=AMOUNT_MIN_VALUE,
        max_value=AMOUNT_MAX_VALUE,
        error_messages={
            'min_value':
                f'Количество не может быть меньше {AMOUNT_MIN_VALUE}.',
            'max_value':
                f'Количество не может превышать {AMOUNT_MAX_VALUE}.',
            'invalid': 'Введите целое число.'
        },
    )


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов."""

    ingredients = RecipeIngredientInputSerializer(required=True, many=True)
    tags = TagPrimaryKeyField(
        required=True,
        many=True,
        queryset=Tag.objects.all()
    )
    image = Base64ImageField(required=True)
    cooking_time = serializers.IntegerField(
        max_value=COOKING_TIME_MIN_VALUE,
        min_value=COOKING_TIME_MAX_VALUE,
        error_messages={
            'min_value':
                ('Время готовки не '
                 f'может быть меньше {COOKING_TIME_MIN_VALUE} минуты'),
            'max_value':
                ('Время готовки не '
                 f'может превышать {COOKING_TIME_MAX_VALUE} минут'),
        }
    )

    class Meta:
        fields = (
            'name',
            'text',
            'ingredients',
            'image',
            'tags',
            'cooking_time',
        )
        model = Recipe

    def validate_ingredients(self, value):
        """Валидация поля Ингредиенты."""
        if not value:
            raise serializers.ValidationError(
                'Поле с ингредиентами не должно быть пустым.'
            )
        if len(value) != len(set(indegrient['id'] for indegrient in value)):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться.'
            )
        return value

    def validate_tags(self, value):
        """Валидация поля Теги."""
        if not value:
            raise serializers.ValidationError(
                'Поле с тегами не должно быть пустым.'
            )

        if len(value) != len(set(tag.id for tag in value)):
            raise serializers.ValidationError(
                'Теги не должны повторяться.'
            )
        return value

    def _update_create_ingredients(recipe, ingredients_data):
        """Метод для обновления и создания ингредиентов."""

        # Удаляем все старые ингредиенты
        recipe.ingredients.clear()

        # Создаем новые связи одной операцией
        RecipeIngredient.objects.bulk_create(
            [
                RecipeIngredient(
                    recipe=recipe,
                    ingredient=ingredient_data['id'],
                    amount=ingredient_data['amount']
                )
                for ingredient_data in ingredients_data
            ]
        )

    def create(self, validated_data):
        """Обработка ингредиентов и тегов."""

        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        with transaction.atomic():
            recipe = super().create(validated_data)
            self._update_create_ingredients(recipe, ingredients_data)
            recipe.tags.set(tags_data)

        return recipe

    def update(self, instance, validated_data):
        """Обработка ингредиентов и тегов."""

        # Извлечение полей с тегами и ингредиентами в отдельные переменные.
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        with transaction.atomic():
            # Обновление основных полей.
            recipe = super().update(instance, validated_data)

            # Обновление тегов.
            instance.tags.set(tags_data)

            # Обновление индегриентов.
            self._update_create_ingredients(recipe, ingredients_data)

        return instance

    def to_representation(self, instance):
        """
        После создания/обновления возвращаем
        данные в формате основного сериализатора.
        """
        return RecipeSerializer(instance, context=self.context).data


class RecipeShortSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор для вывода короткой информации о рецептах."""

    image = Base64ImageField(read_only=True)

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionSerializer(UserSerializer):
    """Сериализатор на основе сериализатора пользователя."""

    recipes = serializers.SerializerMethodField(read_only=True)
    recipes_count = serializers.SerializerMethodField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count',)
        read_only_fields = ('email', 'username', 'first_name', 'last_name')

    def get_recipes_count(self, obj):
        """Подсчет количества рецептов."""
        return obj.recipes.count()

    def get_recipes(self, obj):
        """Получение рецепта."""

        request = self.context['request']
        if not request:
            return {}
        limit = request.query_params.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[:int(limit)]
        return RecipeShortSerializer(
            recipes,
            many=True,
            read_only=True,
            context={'request': request}
        ).data


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Избранные"""

    recipe = RecipeShortSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(
        default=serializers.CurrentUserDefault(),
        read_only=True,
    )

    class Meta:
        model = Favorite
        fields = (
            'recipe',
            'user',
        )
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Favorite.objects.all(),
                fields=('recipe','user',),
                message='Рецепт уже в избранном.'
            )
        ]

    def validate_recipe(self, value):
        if not Recipe.objects.filter(id=value.id).exists():
            raise serializers.ValidationError('Рецепта не существует.')
