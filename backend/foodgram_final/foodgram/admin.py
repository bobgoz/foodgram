from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.contrib.auth.admin import UserAdmin

from foodgram.models import (
    Ingredient,
    Recipe,
    Tag,
    Favorite,
    RecipeIngredient,
    ShoppingCart,
    Subscription,
)

User = get_user_model()


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Настройка админки для избранных."""

    list_display = (
        'user',
        'recipe',
        'added_at',
    )

    search_fields = (
        'user__username',
        'recipe__name',
    )


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    """Настройка админки для Ингредиентов в рецептах."""

    list_display = (
        'ingredient',
        'recipe',
        'amount',
    )

    search_fields = (
        'recipe__name',
        'ingredient__name',
    )



@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Настройка админки для корзины покупок."""

    list_display = (
        'recipe',
        'user',
        'added_at',
    )

    search_fields = (
        'recipe__name',
        'user__username',
    )



@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Настройка админки для подписок."""

    list_display = (
        'user',
        'author',
        'created_at',
    )

    search_fields = (
        'author__username',
        'user__username',
    )


@admin.register(User)
class UserAdmin(UserAdmin):
    """Настройка админки для модели пользователя."""

    list_display = (
        'username',
        'id',
        'first_name',
        'last_name',
        'email',
        'avatar',
        'is_active',
        'password',
    )
    search_fields = (
        'email',
        'username',
        'first_name',
        'last_name',
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Настройка админки для тегов."""

    list_display = ('id', 'name', 'slug',)

    search_fields = ('name', 'slug',)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Настройка админки для ингредиентов."""

    list_display = ('measurement_unit', 'name',)
    search_fields = ('name',)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Настройка админки для рецептов."""

    list_display = (
        'id',
        'name',
        'author',
        'text',
        'image',
        'cooking_time',
        'short_link',
        'created_at',
        'get_favorites_count',
    )
    search_fields = (
        'author__username',
        'name',
        'text',
        'ingredients__name',
        'tags__name',
        'cooking_time',
    )
    list_filter = (
        ('tags', admin.RelatedOnlyFieldListFilter),
    )
    readonly_fields = ('get_favorites_count',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_favorites_count=Count('favorites'))

    @admin.display(description='Добавлений в избранное')
    def get_favorites_count(self, obj):
        return getattr(obj, '_favorites_count', 0)
