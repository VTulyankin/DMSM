from django.urls import path
from .views import RegisterView, LoginView, LinkProfileView, ResetPasswordView, UserProfileView
from django.contrib.auth.views import LogoutView

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('link/<str:token>/', LinkProfileView.as_view(), name='link'),
    path('reset_password/', ResetPasswordView.as_view(), name='reset_password'),
    path('<str:nickname>/', UserProfileView.as_view(), name='profile'),
]
