from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import ProfessionalProfile, Booking
from .models import JobOpening
admin.site.register(JobOpening)
User = get_user_model()

# 1. Create the "Inline" box for the Professional Profile
class ProfessionalProfileInline(admin.StackedInline):
    model = ProfessionalProfile
    can_delete = False
    verbose_name_plural = 'Professional Profile Data'

# 2. Attach the Inline box to the standard User admin page
class UserAdmin(BaseUserAdmin):
    inlines = (ProfessionalProfileInline,)

# 3. Safely re-register the updated models
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, UserAdmin)
admin.site.register(Booking)