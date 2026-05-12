DEFAULT_PAGE = 1
DEFAULT_LIMIT = 10
MAX_LIMIT = 100


def get_pagination(page: int | None, limit: int | None) -> tuple[int, int, int]:
    page = page or DEFAULT_PAGE
    limit = limit or DEFAULT_LIMIT
    if page < 1:
        page = DEFAULT_PAGE
    if limit < 1:
        limit = DEFAULT_LIMIT
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT
    offset = (page - 1) * limit
    return page, limit, offset
