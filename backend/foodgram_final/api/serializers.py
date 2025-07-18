from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from rest_framework import serializers
from rest_framework import validators
from djoser.serializers import UserSerializer
from drf_extra_fields.fields import Base64ImageField

from foodgram.models import (
    Recipe,
    Tag,
    Ingredient,
    RecipeIngredient,
    Favorite,
    ShoppingCart,
    Subscription,
)

from .constants import (
    AMOUNT_MIN_VALUE,
    AMOUNT_MAX_VALUE,
    COOKING_TIME_MIN_VALUE,
    COOKING_TIME_MAX_VALUE,
)
from .mixins import (
    RecipePrimaryKeyMixin,
    AuthorPrimaryKeyMixin,
    BaseDeleteMixin,
    BaseCreateMixin,
)

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
    avatar = Base64ImageField(required=False)

    class Meta:
        model = User
        fields = UserSerializer.Meta.fields + ('is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        """Возвращает булево значение в зависимости от наличия подписки."""
        request = self.context['request']
        if not request.user.is_authenticated:
            return False
        return obj.following.filter(user=request.user).exists()


class IngredientRecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для промежуточной модели ИнгредиентРецепт."""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Рецепты. """

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientRecipeSerializer(
        many=True,
        source='recipe_ingredients',
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField(read_only=True)

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
        error_messages={
            'does_not_exist': 'Ингредиента с таким id не существут.',
        }
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
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        error_messages={
            'does_not_exist': 'Тэга с таким id не существует.',
        },
        many=True,
        required=True,
    )
    image = Base64ImageField(required=True)
    cooking_time = serializers.IntegerField(
        max_value=COOKING_TIME_MAX_VALUE,
        min_value=COOKING_TIME_MIN_VALUE,
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

    def validate(self, attrs):
        """Дополнительная валидация."""
        if 'ingredients' not in attrs:
            raise serializers.ValidationError(
                'Поле ingredient обязательно.'
            )

        if 'tags' not in attrs:
            raise serializers.ValidationError(
                'Поле tags обязательно.'
            )
        return attrs

    def validate_tags(self, value):
        """Валидация поля Тэги"""
        if not value:
            raise serializers.ValidationError(
                'Поле не должно быть пустым.'
            )
        return value

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

    def _update_create_ingredients(self, recipe, ingredients_data):
        """Метод для обновления и создания ингредиентов."""

        recipe.ingredients.clear()

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

    @transaction.atomic
    def create(self, validated_data):
        """Обработка ингредиентов и тегов."""

        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        recipe = super().create(validated_data)
        recipe.tags.set(tags_data)
        self._update_create_ingredients(recipe, ingredients_data)

        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обработка ингредиентов и тегов."""

        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        recipe = super().update(instance, validated_data)
        instance.tags.set(tags_data)
        self._update_create_ingredients(recipe, ingredients_data)

        return instance

    def to_representation(self, instance):
        """
        После создания/обновления возвращаем
        данные в формате основного сериализатора.
        """
        return RecipeSerializer(
            instance,
            context=self.context,
        ).data


class RecipeShortSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор для вывода короткой информации о рецептах."""

    image = Base64ImageField(read_only=True)

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionDeleteSerializer(
    AuthorPrimaryKeyMixin,
    BaseDeleteMixin,
    serializers.Serializer,
):
    """
    Сериализатор для удаления подписки.
    """

    relation_model = Subscription
    relation_field = 'author'
    not_found_message = 'Вы не подписаны на иэтого пользователя.'


class SubscriptionCreateSerializer(
    AuthorPrimaryKeyMixin,
    serializers.ModelSerializer,
):
    """
    Сериализатор для создания подписки.
    """

    author = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        error_messages={
            'does_not_exist': 'Автора с таким id не существует.',
        }
    )

    class Meta:
        model = Subscription
        fields = ('user', 'author',)
        validators = [
            validators.UniqueTogetherValidator(
                queryset=Subscription.objects.all(),
                fields=('user', 'author',),
                message='Вы уже подписаны на этого пользователя.',
            )
        ]

    def validate_author(self, value):
        """Валидация перед созданием подписки."""
        user = self.context['request'].user

        if user == value:

            raise serializers.ValidationError(
                'Нельзя подписаться на себя.'
            )

        return value

    def to_representation(self, instance):
        author = User.objects.annotate(
            recipes_count=Count('recipes')
        ).get(pk=instance.author.pk)

        return SubscriptionShowSerializer(
            author,
            context=self.context,
        ).data


class SubscriptionShowSerializer(UserSerializer):
    """
    Сериализатор для вывода данных о пользователе, на которого
    подписан текущий пользователь, и его рецептах на основе
    сериализатора пользователя.
    """

    recipes = serializers.SerializerMethodField(read_only=True)
    recipes_count = serializers.IntegerField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            'recipes',
            'recipes_count',
        )

    def get_recipes(self, obj):
        """Получение рецепта."""
        request = self.context['request']
        limit = request.query_params.get('recipes_limit')
        recipes = obj.recipes.all()

        if limit:
            recipes = recipes[:int(limit)]

        return RecipeShortSerializer(
            recipes,
            many=True,
            context=self.context,
        ).data


class FavoriteCreateSerializer(
    RecipePrimaryKeyMixin,
    BaseCreateMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для создания избранных."""

    relation_model = Favorite
    message = 'Рецепт уже в избранном.'


class FavoriteDeleteSerializer(
    RecipePrimaryKeyMixin,
    BaseDeleteMixin,
    serializers.Serializer,
):
    """Сериализатор для удаления из избранных"""

    relation_model = Favorite
    relation_field = 'recipe'
    not_found_message = 'Рецепта нет в избранном для удаления.'


class ShoppingCartDeleteSerializer(
    RecipePrimaryKeyMixin,
    BaseDeleteMixin,
    serializers.Serializer,
):
    """Сериализатор для удаления из Корзины покупок."""

    relation_model = ShoppingCart
    relation_field = 'recipe'
    not_found_message = 'Нет рецепта в корзине покупок для удаления.'


class ShoppingCartSerializer(
    RecipePrimaryKeyMixin,
    BaseCreateMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для Корзины покупок."""

    relation_model = ShoppingCart
    message = 'Рецепт уже в корзине покупок.'


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для аватара"""

    avatar = Base64ImageField(
        required=True,
    )

    class Meta:
        model = User
        fields = ('avatar',)

    def validate(self, attrs):
        if 'avatar' not in attrs:
            raise serializers.ValidationError('Поле с аватаром обязательно.')
        return attrs

    def update(self, instance, validated_data):
        instance.avatar = validated_data.get('avatar', instance.avatar)
        instance.save()
        return instance
