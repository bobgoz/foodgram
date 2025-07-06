from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.response import Response
from djoser.serializers import UserSerializer
from drf_extra_fields.fields import Base64ImageField

from foodgram.models import Recipe, Tag, Ingredient, Token

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


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Рецепты. """

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = serializers.SerializerMethodField()
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

    def get_ingredients(self, obj):
        """Получает список ингредиентов для вывода."""
        ingredients = obj.ingredients.through.objects.filter(recipe=obj)
        return [{
            'id': ing.ingredient.id,
            'name': ing.ingredient.name,
            'measurement_unit': ing.ingredient.measurement_unit,
            'amount': ing.amount
        } for ing in ingredients]

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

    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class TagPrimaryKeyField(serializers.PrimaryKeyRelatedField):
    """
    Кастомное поле PrimaryKeyRelatedField, которое обрабатывает как
    обычные значения первичного ключа, так и словари с полем 'id'.

    - Если входные данные — словарь (например, `{'id': 123}`), извлекает
      значение `id
      и проверяет его как первичный ключ.
    - Если входные данные — обычное значение (например, `123`), проверяет его
      стандартным способом.

    Полезно для API, которые могут получать ссылки на теги в разных форматах:
    как простые ID, так и вложенные объекты с ID.
    """

    def to_internal_value(self, data):
        if isinstance(data, dict):
            return super().to_internal_value(data['id'])
        return super().to_internal_value(data)


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов."""

    ingredients = RecipeIngredientInputSerializer(required=True, many=True)
    tags = TagPrimaryKeyField(
        required=True,
        many=True,
        queryset=Tag.objects.all()
    )
    image = Base64ImageField(required=True)

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

    def validate(self, data):
        if self.context['request'].method == 'PATCH':

            if 'ingredients' not in data:
                raise serializers.ValidationError(
                    {'ingredients': 'Обязательное поле'})
            if 'tags' not in data:
                raise serializers.ValidationError(
                    {'tags': 'Обязательное поле'})
        return data

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

    def validate_cooking_time(self, value):
        """
        Проверяем, что время приготовления больше нуля.
        """
        if value == 0:
            raise serializers.ValidationError(
                "Время приготовления должно быть больше нуля"
            )
        return value

    def create(self, validated_data):
        """Обработка ингредиентов и тегов."""

        try:
            ingredients_data = validated_data.pop('ingredients')
            tags_data = validated_data.pop('tags')

            recipe = Recipe.objects.create(
                **validated_data
            )
        except IntegrityError as e:
            return Response(
                {'error': {e}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Создание связей с ингредиентами.
        for ingredient_data in ingredients_data:
            recipe.ingredients.add(
                ingredient_data['id'],
                through_defaults={'amount': ingredient_data['amount']}
            )

        recipe.tags.set(tags_data)

        return recipe

    def update(self, instance, validated_data):
        """Обработка ингредиентов и тегов."""

        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        # Обновляем основные поля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Обновляем теги если они пришли
        if tags_data is not None:
            instance.tags.set(tags_data)

        # Обновляем ингредиенты если они пришли
        if ingredients_data is not None:
            instance.ingredients.clear()
            for ingredient_data in ingredients_data:
                instance.ingredients.add(
                    ingredient_data['id'],
                    through_defaults={'amount': ingredient_data['amount']}
                )

        return instance

    def to_representation(self, instance):
        """
        После создания/обновления возвращаем
        данные в формате основного сериализатора.
        """
        return RecipeSerializer(instance, context=self.context).data


class RecipeShortSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор для вывода короткой информации о рецептах."""

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


class TokenSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Token"""

    class Meta:
        model = Token
        fields = '__all__'
        extra_kwargs = {'full_url': {'validators': []}}

    def create(self, validated_data):
        """Создание токена """

        full_url = validated_data['full_url']

        token, created = Token.objects.get_or_create(full_url=full_url)
        if created:
            status_code = status.HTTP_201_CREATED
        else:
            status_code = status.HTTP_200_OK
        return Token, status_code


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Избранные"""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'image',
            'cooking_time',
        )

    def get_image(self, obj):
        if obj.image:
            return self.context["request"].build_absolute_uri(obj.image.url)
        return None
