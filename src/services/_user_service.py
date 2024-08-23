import peewee
from starlette.exceptions import HTTPException

from src.config.base_service import BaseService
from src.models import db_models
from src.models.db_models import UsersModel, UserGroupModel, GroupModel
from src.models.dto.user_dto import UserDto, CreateUserRequest
from src.services.password_manager import PasswordManager


class UserService(BaseService):
    def __init__(self):
        pass

    def create_user(self, request: CreateUserRequest):
        try:
            with db_models.BaseModel._meta.database.atomic():
                user = UsersModel.create(
                    password_hash=PasswordManager.hash_password(
                        password=request.password
                    ),
                    email=request.email,
                )

                UserGroupModel.create(user=user, group=GroupModel.get(name="player"))

                return {"email": user.email}
        except peewee.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"The e-mail address {request.email} is already in the system. Please use a different e-mail or login.",
            )

    def get_user_by_id(self, id: int):
        try:
            user = UsersModel.get_by_id(id)
            groups = (
                GroupModel.select()
                .join(UserGroupModel)
                .where(UserGroupModel.user == user.team_id)
            )

            return UserDto(
                email=user.email, groups=[group.team_name for group in groups]
            )
        except peewee.DoesNotExist:
            raise HTTPException(
                status_code=404, detail=f"User {id} not found in database."
            )

    def get_user_by_email(self, email: str):
        try:
            user = UsersModel.get(UsersModel.email == email)
            groups = (
                GroupModel.select()
                .join(UserGroupModel)
                .where(UserGroupModel.user == user.team_id)
            )

            return UserDto(
                email=user.email, groups=[group.team_name for group in groups]
            )
        except peewee.DoesNotExist:
            raise HTTPException(
                status_code=404, detail=f"User {email} not found in database."
            )

    def add_user_to_group(self, user_id: int, group_id: int):
        try:
            UserGroupModel.create(user=user_id, group=group_id)
            return self.get_user_by_id(id=user_id)

        except Exception:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add user {user_id} to group {group_id}",
            )
