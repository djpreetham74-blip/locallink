"""
URL configuration for locallink_core project.
"""
from django.contrib import admin
from django.urls import path
from users import views

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # Core Pages
    path('', views.home, name='home'),
    path('category/<str:profession_slug>/', views.profession_detail, name='profession_detail'),
    path('profile/<int:pro_id>/', views.professional_detail, name='profile_detail'),

    # Authentication
    path('signup/', views.signup, name='signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Dashboard & Bookings
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('booking/<int:pro_id>/', views.book_professional, name='book_professional'),
    path('checkout/', views.checkout, name='checkout'),
    # Add this under the Dashboard & Bookings section
    path('booking/<int:booking_id>/review/', views.leave_review, name='leave_review'),
    # NEW: Dynamic Status Route (Replaces cancel_booking)
    path('booking/<int:booking_id>/status/<str:new_status>/', views.update_booking_status, name='update_booking_status'),

    # AI API Endpoints
    path('api/chat/', views.ai_chat_api, name='ai_chat_api'),
    path('api/polish/', views.ai_magic_polish, name='ai_polish'),
    # Add this to your AI API Endpoints section
    path('api/analyze-image/', views.api_analyze_image, name='api_analyze_image'),
]