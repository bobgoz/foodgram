from rest_framework.exceptions import ValidationError


def validate_forbidden_usernames(value):
    """Валидатор, исключающий недопустимые username."""

    forbidden_usernames = ['me', 'root', 'admin']

    if value.lower() in forbidden_usernames:
        raise ValidationError(
            f"Username '{value}' запрещено для использования."
        )