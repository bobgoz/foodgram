from rest_framework.permissions import (
    BasePermission,
    SAFE_METHODS,
)


class CustomPermission(BasePermission):
    """Пермишен для проверки, что рецепт принадлежит автору."""
    def has_permission(self, request, view):
        # Ограничение для отдельного эндпоинта
        if view.action == 'me':
            return request.user.is_authenticated
        return (request.method in SAFE_METHODS
                or request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return (request.method in SAFE_METHODS
                or obj.author == request.user)
