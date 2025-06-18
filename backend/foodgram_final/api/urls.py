from rest_framework.routers import SimpleRouter, DefaultRouter

from .views import (RecipeViewSet, 
                    IngredientViewSet, 
                    TagViewSet,
                    CustomUserViewSet,
                )

router = DefaultRouter()

router.register('recipes', RecipeViewSet)
router.register('tags', TagViewSet)
router.register('ingredients', IngredientViewSet)
router.register('users', CustomUserViewSet)
