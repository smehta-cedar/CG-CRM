from rest_framework.pagination import PageNumberPagination

from .response import APIResponse


class StandardPagination(PageNumberPagination):
    """?page=2&page_size=50, answered with the success envelope plus meta."""

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data, message=''):
        paginator = self.page.paginator
        return APIResponse(
            data=data,
            message=message,
            meta={
                'page': self.page.number,
                'page_size': paginator.per_page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            },
        )


def paginate(request, queryset, serializer_class, message=''):
    """One page of `queryset`, serialized and wrapped in the envelope.

        return paginate(request, users, UserSerializer, 'Users fetched successfully.')
    """
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(serializer_class(page, many=True).data, message=message)
