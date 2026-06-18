from django.shortcuts import render

def custom_error_view(request, exception=None, status=500):
    messages = {
        404: "Страница не найдена",
        500: "Внутренняя ошибка сервера",
        403: "Доступ запрещен",
        400: "Некорректный запрос"
    }
    context = {
        'error_code': status,
        'error_message': messages.get(status, "Произошла непредвиденная ошибка")
    }
    return render(request, 'error.html', context, status=status)

def error_404(request, exception):
    return custom_error_view(request, exception, status=404)

def error_500(request, exception=None):
    return custom_error_view(request, exception, status=500)

def error_403(request, exception):
    return custom_error_view(request, exception, status=403)

def error_400(request, exception):
    return custom_error_view(request, exception, status=400)
