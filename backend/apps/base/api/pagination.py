from rest_framework.pagination import PageNumberPagination

from .response import APIResponse


class StandardPagination(PageNumberPagination):
    """?page=2&page_size=50, answered with the success envelope plus meta."""

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_meta(self):
        paginator = self.page.paginator
        return {
            'page': self.page.number,
            'page_size': paginator.per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
        }

    def get_paginated_response(self, data, message=''):
        return APIResponse(data=data, message=message, meta=self.get_meta())


def paginate(request, queryset):
    """One page of `queryset`, and the meta that describes it.

        page, meta = paginate(request, users)
        serializer = UserSerializer(page, many=True)
        return APIResponse(serializer.data, 'Users fetched successfully.', meta=meta)
    """
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return page, paginator.get_meta()
