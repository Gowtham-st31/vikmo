from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError, NotFound, MethodNotAllowed, ParseError
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        code = "VALIDATION_ERROR"
        message = str(exc)
        details = []

        if response.status_code == 404:
            code = "NOT_FOUND"
            message = "Not found."
        elif response.status_code == 400:
            code = "VALIDATION_ERROR"
            message = "Validation error"
            if isinstance(response.data, dict):
                for k, v in response.data.items():
                    if isinstance(v, list):
                        for err in v:
                            details.append({"field": k, "error": str(err)})
                    else:
                        details.append({"field": k, "error": str(v)})
            elif isinstance(response.data, list):
                for err in response.data:
                    details.append({"error": str(err)})
        elif response.status_code == 405:
            code = "METHOD_NOT_ALLOWED"
            message = "Method not allowed."
        elif response.status_code == 401 or response.status_code == 403:
            code = "UNAUTHORIZED"
            message = "Authentication credentials were not provided."
        
        # Allow exceptions to carry a custom error code
        if hasattr(exc, 'custom_code'):
            code = exc.custom_code
        elif hasattr(exc, 'default_code') and isinstance(exc.default_code, str) and exc.default_code.isupper():
            code = exc.default_code
        
        if hasattr(exc, 'custom_message'):
            message = exc.custom_message
        if hasattr(exc, 'custom_details'):
            details = exc.custom_details

        response.data = {
            "error": {
                "code": code,
                "message": message,
                "details": details
            }
        }

    return response
