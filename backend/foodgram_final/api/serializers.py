from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.validators import RegexValidator
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _

from drf_base64.fields import Base64ImageField

from rest_framework import serializers
from rest_framework import status
from rest_framework.validators import UniqueValidator
from rest_framework.response import Response

from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer

from foodgram.models import Recipe, Tag, Ingredient
from .validators import validate_forbidden_usernames
from .utils import send_confirm_mail

from drf_base64.fields import Base64ImageField

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


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name', 'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        # Логика проверки подписки
        # request = self.context.get('request')
        # if request and request.user.is_authenticated:
        #     return obj.following.filter(user=request.user).exists()
        return False

    def get_avatar(self, obj):
        if obj.avatar:
            return self.context['request'].build_absolute_uri(obj.avatar.url)
        return None


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
            'name',
            'text',
            'ingredients',
            'image',
            'tags',
            'cooking_time',
        )
        model = Recipe

    def get_ingredients(self, obj):
        ingredients = obj.ingredients.through.objects.filter(recipe=obj)
        return [{
            'id': ing.ingredient.id,
            'name': ing.ingredient.name,
            'measurement_unit': ing.ingredient.measurement_unit,
            'amount': ing.amount
        } for ing in ingredients]

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.favorites.filter(user=request.user).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.shopping_carts.filter(user=request.user).exists()
        return False


class RecipeIngredientInputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов."""

    ingredients = RecipeIngredientInputSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(
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

    def create(self, validated_data):
        """Обработка ингредиентов и тегов."""

        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        recipe = Recipe.objects.create(
            **validated_data
        )
        

        # Создание связей с ингредиентами.
        for ingredient_data in ingredients_data:
            recipe.ingredients.add(
                ingredient_data['id'],
                through_defaults={'amount': ingredient_data['amount']}
            )

        # Добавление тегов.
        recipe.tags.set(tags_data)

        return recipe

    def update(self, instance, validated_data):
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
        # После создания/обновления возвращаем 
        # данные в формате основного сериализатора
        return RecipeSerializer(instance, context=self.context).data
