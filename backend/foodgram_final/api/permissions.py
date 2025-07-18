from rest_framework.permissions import (
    SAFE_METHODS,
    IsAuthenticatedOrReadOnly
)


class CustomPermission(IsAuthenticatedOrReadOnly):
    """Пермишен для проверки, что рецепт принадлежит автору."""

    def has_object_permission(self, request, view, obj):
        return (request.method in SAFE_METHODS
                or obj.author == request.user)
