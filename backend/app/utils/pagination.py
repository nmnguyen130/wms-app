import math

from fastapi import Query
from pydantic import BaseModel


class PaginationParams(BaseModel):
    page: int = Query(1, ge=1, description="Page number (1-indexed)")
    limit: int = Query(20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    limit: int
    total_pages: int


def paginate[T](items: list[T], total: int, params: PaginationParams) -> PaginatedResponse[T]:
    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        limit=params.limit,
        total_pages=math.ceil(total / params.limit),
    )
