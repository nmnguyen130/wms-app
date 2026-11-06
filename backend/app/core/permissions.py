from enum import StrEnum

from app.core.exceptions import AppException


class Role(StrEnum):
    ADMIN = "ADMIN"
    WAREHOUSE_MANAGER = "WAREHOUSE_MANAGER"
    INVENTORY_CLERK = "INVENTORY_CLERK"
    QC_INSPECTOR = "QC_INSPECTOR"
    SAMPLE_CUSTODIAN = "SAMPLE_CUSTODIAN"
    PROCUREMENT_STAFF = "PROCUREMENT_STAFF"
    SALES_STAFF = "SALES_STAFF"
    OPERATOR = "OPERATOR"


class Permission(StrEnum):
    USERS_MANAGE = "users:manage"
    CATALOG_READ = "catalog:read"
    CATALOG_WRITE = "catalog:write"
    PARTNERS_READ = "partners:read"
    PARTNERS_WRITE = "partners:write"


_CATALOG_READ_WRITE = frozenset({Permission.CATALOG_READ, Permission.CATALOG_WRITE})
_CATALOG_READ_ONLY = frozenset({Permission.CATALOG_READ})
_PARTNERS_READ_WRITE = frozenset({Permission.PARTNERS_READ, Permission.PARTNERS_WRITE})
_PARTNERS_READ_ONLY = frozenset({Permission.PARTNERS_READ})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.WAREHOUSE_MANAGER: _CATALOG_READ_WRITE | _PARTNERS_READ_WRITE,
    Role.INVENTORY_CLERK: _CATALOG_READ_ONLY | _PARTNERS_READ_ONLY,
    Role.QC_INSPECTOR: _CATALOG_READ_WRITE | _PARTNERS_READ_ONLY,
    Role.SAMPLE_CUSTODIAN: _CATALOG_READ_ONLY | _PARTNERS_READ_ONLY,
    Role.PROCUREMENT_STAFF: _CATALOG_READ_WRITE | _PARTNERS_READ_WRITE,
    Role.SALES_STAFF: _CATALOG_READ_WRITE | _PARTNERS_READ_WRITE,
    Role.OPERATOR: _CATALOG_READ_ONLY | _PARTNERS_READ_ONLY,
}


def has_permission(role: str | Role, permission: Permission) -> bool:
    try:
        role_enum = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(role_enum, frozenset())


def enforce_permission(role: str | Role, permission: Permission) -> None:
    if not has_permission(role, permission):
        raise AppException.forbidden("Insufficient permissions to perform this action")
