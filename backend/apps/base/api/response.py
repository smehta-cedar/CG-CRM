from rest_framework import status as http_status
from rest_framework.response import Response


class APIResponse(Response):
    """The success envelope every view returns.

        {
            "success": true,
            "message": "Users fetched successfully.",
            "data": ...,
            "meta": {...}          # only on paginated lists
        }

        return APIResponse(serializer.data, 'User created successfully.', status=201)
    """

    def __init__(self, data=None, message='', status=http_status.HTTP_200_OK, meta=None, headers=None):
        body = {'success': True, 'message': message, 'data': data}
        if meta is not None:
            body['meta'] = meta
        super().__init__(data=body, status=status, headers=headers)


def error_body(message, code, errors=None):
    """The error envelope, built by the exception handler.

        {
            "success": false,
            "message": "Invalid input.",
            "code": "invalid",
            "errors": {"email": ["Enter a valid email address."]}   # or null
        }
    """
    return {'success': False, 'message': message, 'code': code, 'errors': errors}
