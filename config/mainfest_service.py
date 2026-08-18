from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def manifest(request):
    return JsonResponse({
        "name": "QIsmartuX",
        "short_name": "QIsmartuX",
        "description": "Manufacturing Control, IPQC, EHS & Workflow System",
        "start_url": "/login/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#0ea5e9",
        "icons": [
            {
                "src": "/static/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })
