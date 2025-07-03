from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import (
    IsAuthenticated,
    BasePermission,
    SAFE_METHODS,
)


class IsRecipeOwnerPermission(BasePermission):
    """Пермишен для проверки, что рецепт принадлежит автору."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.author == request.user


class CustomPermission(IsAuthenticated):
    """Кастомный пермишен, который выбрасывает исключение 401 Unauthorized."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated(
                detail="Требуется авторизация.",
                code="not_authentica",
            )
        return True
