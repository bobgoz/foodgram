from rest_framework.routers import SimpleRouter

from .views import (RecipeViewSet, 
                    IngredientViewSet, 
                    TagViewSet, 
                    UserViewSet, 
                    AuthViewSet,
                )

router = SimpleRouter()

router.register('recipes', RecipeViewSet)
router.register('tags', TagViewSet)
router.register('users', UserViewSet)
router.register('ingredients', IngredientViewSet)
router.register('auth/token', AuthViewSet, basename='auth')
