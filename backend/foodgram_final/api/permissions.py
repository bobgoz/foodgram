from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import (
    IsAuthenticated,
    BasePermission,
    SAFE_METHODS,
)


class IsRecipeOwnerPermission(BasePermission):
    """Пермишен для проверки, что рецепт принадлежит автору."""
    def has_permission(self, request, view):

        return (request.method in SAFE_METHODS
                or request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):

        return (request.method in SAFE_METHODS
                or obj.author == request.user)
