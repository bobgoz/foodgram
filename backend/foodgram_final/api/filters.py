from django_filters.rest_framework import filters, FilterSet
from django.contrib.auth import get_user_model

from foodgram.models import Recipe

User = get_user_model()


class RecipeFilter(FilterSet):
    """Фильтра для эндпоинта api/recipes/ """

    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
    author = filters.ModelChoiceFilter(queryset=User.objects.all())
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        if value is True:
            return queryset.filter(favorites__user=self.request.user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if value is True:
            return queryset.filter(
                in_shopping_carts__user=self.request.user)
        elif value is False:
            return queryset.exclude(
                in_shopping_carts__user=self.request.user)
        return queryset

    class Meta:
        model = Recipe
        fields = ('tags', 'author', 'is_favorited', 'is_in_shopping_cart')
