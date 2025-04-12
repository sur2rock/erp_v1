@echo off

:: List of apps
set CORE_APP=core
set APPS=herd finance inventory operations hr assets reports forecasting configuration

:: Create urls.py for core app
echo Creating urls.py for app: %CORE_APP%
(
    echo from django.urls import path
    echo from . import views
    echo.
    echo app_name = '%CORE_APP%'
    echo.
    echo urlpatterns = [
    echo     path('', views.dashboard, name='dashboard'),
    echo     path('login/', views.login_view, name='login'),
    echo     path('logout/', views.logout_view, name='logout'),
    echo ]
) > %CORE_APP%\urls.py

:: Loop through the rest of the apps and create urls.py
for %%A in (%APPS%) do (
    echo Creating urls.py for app: %%A
    (
        echo from django.urls import path
        echo from . import views
        echo.
        echo app_name = '%%A'
        echo.
        echo urlpatterns = [
        echo     # We'll add URL patterns later
        echo ]
    ) > %%A\urls.py
)

echo All urls.py files have been created successfully!
pause