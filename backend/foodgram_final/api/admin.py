from django.contrib import admin

from foodgram.models import Ingredient, Recipe, Tag


class TagAdmin(admin.ModelAdmin):

    list_display = ('id', 'name', 'slug',)


class IngredientAdmin(admin.ModelAdmin):

    list_display = ('measurement_unit', 'name',)


class RecipeAdmin(admin.ModelAdmin):

    list_display = (
        'author',
        'name',
        'text',
        'image',
        'cooking_time',
        'short_link',
    )


admin.site.register(Tag, TagAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Recipe, RecipeAdmin)
