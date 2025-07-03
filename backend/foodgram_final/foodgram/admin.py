from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count

from foodgram.models import Ingredient, Recipe, Tag, Token

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Настройка админки для модели пользователя."""

    list_display = (
        'id',
        'email',
        'username',
        'avatar',
        'is_subscribed',
        'is_active',
        'first_name',
        'last_name',
    )
    search_fields = ('email', 'username',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):

    list_display = ('id', 'name', 'slug',)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):

    list_display = ('measurement_unit', 'name',)
    search_fields = ('name',)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'author',
        'name',
        'text',
        'image',
        'cooking_time',
        'short_link',
        'created_at',
        'get_favorites_count',
    )
    search_fields = ('author', 'name',)
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


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    """Настройки админки для модели Token"""

    list_display = (
        'full_url',
        'short_url',
        'requests_count',
        'created_at',
        'is_active',
    )
    search_fields = ('full_url', 'short_url')
    ordering = ('-created_at',)
