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
    ShoppingCart,
    Subscription,
)

from .constants import (
    AMOUNT_MIN_VALUE,
    AMOUNT_MAX_VALUE,
    COOKING_TIME_MIN_VALUE,
    COOKING_TIME_MAX_VALUE,
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
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )

    def validate(self, data):
        """Валидация подписок."""

        request = self.context.get('request')
        author = self.context.get('author')
        user = request.user
        subscription = Subscription.objects.filter(user=user, author=author)

        if request.method == 'POST':
            if user == author:
                raise serializers.ValidationError(
                    {'error': 'Нельзя подписаться на самого себя.'}
                )

            if subscription.exists():
                raise serializers.ValidationError(
                    {'error': 'Вы уже подписаны на этого пользователя.'}
                )

        elif request.method == 'DELETE':
            if not subscription.exists():
                raise serializers.ValidationError(
                    {'error': 'Такой подписки не существует.'}
                )

        return data

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
    tags = serializers.ListField(required=True)
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

    def validate_image(self, value):
        """Валидация поля image"""
        if not value:
            raise serializers.ValidationError(
                'Поле обязательно.'
            )
        return value

    def validate(self, attrs):
        """Дополнительная валидация."""
        if not attrs.get('ingredients'):
            raise serializers.ValidationError(
                'Поле ingredient обязательно.'
            )

        if not attrs.get('tags'):
            raise serializers.ValidationError(
                'Поле tags обязательно.'
            )
        return attrs

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
        if not Tag.objects.filter(id__in=value).exists():
            raise serializers.ValidationError(
                'Таких тегов нет.'
            )

        tag_list = [tag for tag in value]
        if len(tag_list) != len(set(tag_list)):
            raise serializers.ValidationError(
                'Теги не должны повторяться.'
            )

        if not value:
            raise serializers.ValidationError(
                'Поле с тегами не должно быть пустым.'
            )
        return value

    def _update_create_ingredients(self, recipe, ingredients_data):
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

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        author = self.instance

        if request.method == 'POST':
            if Subscription.objects.filter(user=user, author=author).exists():
                raise serializers.ValidationError(
                    'Вы уже подписаны на этого пользователя.',
                    code='duplicate',
                )

        if user == author:
            raise serializers.ValidationError(
                'Нельзя подписаться на себя.'
            )

        return attrs

    def create(self, validated_data):
        """Создание подписки."""
        return Subscription.objects.create(
            author=self.context.get('author'),
            user=self.context.get('user')
        )

    def get_recipes_count(self, obj):
        """Подсчет количества рецептов."""
        return obj.recipes.count()

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
            read_only=True,
            context={'request': request}
        ).data


class FavoriteSerializer(serializers.Serializer):
    """Сериализатор для модели Избранные"""

    recipe = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(),
    )
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
                fields=('recipe', 'user'),
                message='Рецепт уже в избранном.',
            ),
        ]

    def validate_recipe(self, value):
        if not Recipe.objects.filter(id=value.id).exists():
            raise serializers.ValidationError('Рецепта не существует.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        recipe = self.context.get('recipe')

        if request.method == 'POST':
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                raise serializers.ValidationError(
                    {"error": "Рецепт уже в избранном."}
                )

        elif request.method == 'DELETE':
            if not Favorite.objects.filter(user=user, recipe=recipe).exists():
                raise serializers.ValidationError(
                    {"error": "Рецепта нет в избранном."}
                )

        return attrs

    def create(self, validated_data):
        return Favorite.objects.create(
            user=self.context['request'].user,
            recipe=self.context['recipe'],
        )

    def to_representation(self, instance):
        return RecipeShortSerializer(
            instance.recipe).data


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для Корзины покупок."""

    recipe = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(),
    )
    user = serializers.PrimaryKeyRelatedField(
        default=serializers.CurrentUserDefault(),
        read_only=True,
    )

    class Meta:
        model = ShoppingCart
        fields = ('id', 'user', 'recipe', 'added_at',)
        read_only_fields = ('user', 'added_at')
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=ShoppingCart.objects.all(),
                fields=('recipe', 'user'),
                message='Рецепт уже в корзине покупок.',
            ),
        ]

    def create(self, validated_data):
        return ShoppingCart.objects.create(
            user=self.context['request'].user,
            recipe=self.context['recipe'],
        )

    def to_representation(self, instance):
        return RecipeShortSerializer(instance.recipe).data


class SubscribeSerializer(serializers.ModelSerializer):
    """Сериализатор для подписок."""

    author = UserSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(
        default=serializers.CurrentUserDefault(),
        read_only=True,
    )

    class Meta:
        model = Subscription
        fields = ('id', 'user', 'author', 'created_at')
        read_only_fields = ('user', 'created_at')
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Subscription.objects.all(),
                fields=('author', 'user'),
                message='Вы уже подписаны на этого автора!',
            ),
            serializers.UniqueTogetherValidator(
                queryset=Subscription.objects.all(),
                fields=('user', 'author'),
                message='Вы уже подписаны на этого автора.'
            ),
        ]


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для аватара"""

    avatar = Base64ImageField(
        required=True,
    )

    class Meta:
        model = User
        fields = ('avatar',)

    def validate(self, attrs):
        if not attrs.get('avatar'):
            raise serializers.ValidationError('Поле с аватаром обязательно.')
        return attrs

    def update(self, instance, validated_data):
        instance.avatar = validated_data.get('avatar', instance.avatar)
        instance.save()
        return instance
