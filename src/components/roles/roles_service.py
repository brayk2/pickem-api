from peewee import DoesNotExist, IntegrityError
from typing import List

from src.components.user.user_exceptions import UserNotFoundException
from src.config.base_service import BaseService
from src.models.new_db_models import GroupModel, UserModel, UserGroupModel
from src.components.roles.roles_exceptions import (
    RoleNotFoundException,
    RoleAlreadyExistsException,
)
from src.components.roles.roles_models import RoleDto
from src.util.injection import dependency


@dependency
class RolesService(BaseService):
    """
    Service class for managing roles and role-related operations.
    """

    def create_role(self, name: str, description: str | None = None) -> RoleDto:
        """
        Creates a new role with the given name and description.

        :param name: The name of the role.
        :param description: An optional description of the role.
        :return: The created RoleDto instance.
        :raises RoleAlreadyExistsException: If a role with the given name already exists.
        """
        self.logger.info(
            f"Attempting to create role '{name}' with description: {description}"
        )
        try:
            role = GroupModel.create(name=name, description=description)
            self.logger.info(f"Role '{name}' created successfully.")
            return RoleDto.model_validate(role)
        except IntegrityError:
            self.logger.error(f"Failed to create role '{name}': Role already exists.")
            raise RoleAlreadyExistsException(role_name=name)

    def get_role(self, role_name: str) -> RoleDto:
        """
        Retrieves a role by its name.

        :param role_name: The name of the role to retrieve.
        :return: The RoleDto instance representing the role.
        :raises RoleNotFoundException: If the role does not exist.
        """
        self.logger.info(f"Fetching role with name '{role_name}'")
        try:
            role = GroupModel.get(GroupModel.name == role_name)
            self.logger.info(f"Role '{role_name}' retrieved successfully.")
            return RoleDto.model_validate(role)
        except DoesNotExist:
            self.logger.error(f"Role '{role_name}' not found.")
            raise RoleNotFoundException(role_name=role_name)

    def delete_role(self, role_name: str) -> None:
        """
        Deletes a role by its name.

        :param role_name: The name of the role to delete.
        :raises RoleNotFoundException: If the role does not exist.
        """
        self.logger.info(f"Deleting role with name '{role_name}'")
        try:
            role = GroupModel.get(GroupModel.name == role_name)
            role.delete_instance()
            self.logger.info(f"Role '{role_name}' deleted successfully.")
        except DoesNotExist:
            self.logger.error(f"Role '{role_name}' not found.")
            raise RoleNotFoundException(role_name=role_name)

    def manage_user_roles(self, username: str, role_name: str) -> List[str]:
        """
        Adds a user to a role and returns the updated list of roles.

        :param username: The username of the user.
        :param role_name: The role to assign to the user.
        :return: A list of role names associated with the user after the role is added.
        :raises UserNotFoundException: If the user does not exist.
        :raises RoleNotFoundException: If the role does not exist.
        """
        self.logger.info(f"Adding user '{username}' to role '{role_name}'")

        user = UserModel.get_or_none(UserModel.username == username)
        if not user:
            self.logger.error(f"User '{username}' not found.")
            raise UserNotFoundException(username=username)

        role = GroupModel.get_or_none(GroupModel.name == role_name)
        if not role:
            self.logger.error(f"Role '{role_name}' not found.")
            raise RoleNotFoundException(role_name=role_name)

        try:
            UserGroupModel.create(user=user, group=role)
        except IntegrityError:
            self.logger.error(f"User '{username}' already has role '{role_name}'")
            raise RoleAlreadyExistsException(role_name=role_name)

        self.logger.info(f"User '{username}' added to role '{role_name}' successfully.")

        # Return the updated list of roles
        return self.get_roles_for_user(user=user)

    def get_roles_for_user(self, user: UserModel) -> List[str]:
        """
        Retrieves the roles associated with a given user.

        :param user: The user instance to retrieve roles for.
        :return: A list of role names associated with the user.
        """
        self.logger.info(f"Fetching roles for user '{user.username}'")
        roles = [user_group.group.name for user_group in user.user_groups]
        self.logger.info(f"Retrieved roles for user '{user.username}': {roles}")
        return roles

    def get_all_roles(self) -> List[RoleDto]:
        """
        Retrieves all roles.

        :return: A list of RoleDto instances.
        """
        self.logger.info("Fetching all roles")
        roles = GroupModel.select()
        role_dtos = [RoleDto.model_validate(role) for role in roles]
        self.logger.info(f"Retrieved {len(role_dtos)} roles.")
        return role_dtos

    def get_default_role(self) -> GroupModel:
        """
        Retrieves the default role to be assigned to new users.

        :return: The default GroupModel instance.
        :raises RoleNotFoundException: If the default role does not exist.
        """
        self.logger.info("Fetching default role")
        try:
            default_role = GroupModel.get(GroupModel.name == "player")
            self.logger.info("Default role 'player' retrieved successfully.")
            return default_role
        except DoesNotExist:
            self.logger.error("Default role 'player' not found.")
            raise RoleNotFoundException(role_name="player")
