from django.urls import path
from dmsm.apps.users import views

app_name = 'users'

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('link/<str:token>/', views.LinkProfileView.as_view(), name='link'),
]
