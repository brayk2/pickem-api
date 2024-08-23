from fastapi import HTTPException, status


class RoleNotFoundException(HTTPException):
    def __init__(self, role_name: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' not found.",
        )


class RoleAlreadyExistsException(HTTPException):
    def __init__(self, role_name: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{role_name}' already exists.",
        )
