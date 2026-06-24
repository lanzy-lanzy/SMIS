from .models import User


def user_profile(request):
    if request.user.is_authenticated:
        return {'user_profile': request.user}
    return {}
