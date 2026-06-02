from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

# This grabs your active custom user model (users.User)
User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields