from django.contrib import admin
from django.urls import path
from tracker import views # Importa tus vistas desde la app tracker

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('api/bus-locations/', views.get_bus_locations, name='bus_locations_api'),
    path('api/rutas/', views.get_rutas, name='rutas_api'),
    path('api/update-location/', views.update_location, name='update_location_api'),
    # NUEVA RUTA: Para el cierre de sesión personalizado
    path('logout/', views.driver_logout_view, name='logout'), 
    path('api/paraderos/', views.get_paraderos, name='api_paraderos'),
    path('api/paradero-info/<int:paradero_id>/', views.paradero_info, name='api_paradero_info'),
]
