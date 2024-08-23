from peewee import DoesNotExist, IntegrityError
from src.components.auth.auth_models import DecodedToken
from src.components.auth.auth_exceptions import InvalidTokenException
from src.components.roles.roles_service import RolesService
from src.components.user.user_exceptions import (
    UserNotFoundException,
    PermissionDeniedException,
    BadRequestException,
)
from src.components.user.user_models import (
    UserDto,
    UpdateUserPasswordRequest,
    UpdateUserRequest,
)
from src.config.base_service import BaseService
from src.models.new_db_models import UserModel
from src.services.oauth_service import OAuthService
from src.util.injection import dependency, inject


@dependency
class UserService(BaseService):
    """
    Service class for managing user-related operations.
    """

    @inject
    def __init__(self, roles_service: RolesService, oauth_service: OAuthService):
        """
        UserService constructor.

        :param roles_service: Injected instance of RolesService for managing user roles.
        """
        self.roles_service = roles_service
        self.oauth_service = oauth_service

    def get_user_by_username(self, username: str) -> UserModel | None:
        """
        Fetches a user by their username.

        :param username: The username to search for.
        :return: UserModel instance if found, None otherwise.
        """
        self.logger.info(f"Fetching user by username: {username}")
        try:
            user = UserModel.get(username=username)
            self.logger.info(f"User '{username}' found.")
            return user
        except DoesNotExist:
            self.logger.error(f"Failed to find user: {username}")
            return None

    def validate_user_from_decoded_token(
        self, decoded_token: DecodedToken
    ) -> DecodedToken:
        """
        Validates the user from the decoded token and updates the roles.

        :param decoded_token: The decoded JWT containing user information.
        :return: The updated DecodedToken with roles.
        :raises InvalidTokenException: If the user does not exist.
        """
        self.logger.info(f"Validating user in system for token: {decoded_token}")

        # Check if the user exists in the system
        if user := self.get_user_by_username(decoded_token.sub):
            # Update roles in the token with the latest roles from the database
            decoded_token.roles = self.roles_service.get_roles_for_user(user)
            return decoded_token

        self.logger.error(f"User not found for token: {decoded_token}")
        raise InvalidTokenException()

    def validate_token(self, encoded_token: str) -> DecodedToken:
        decoded_token = self.oauth_service.decode_token(encoded_token)
        return self.validate_user_from_decoded_token(decoded_token)

    def create_user(self, username: str, email: str, password_hash: str) -> UserModel:
        """
        Creates a new user and assigns the default role.

        :param username: The username for the new user.
        :param email: The email for the new user.
        :param password_hash: The hashed password for the new user.
        :return: The created UserModel instance.
        """
        self.logger.info(f"Creating user: {username}")
        user = UserModel.create(
            username=username, email=email, password_hash=password_hash
        )
        self.logger.info(f"Assigning default role to user: {username}")
        default_role = self.roles_service.get_default_role()
        self.add_user_to_role(username=user.username, role_name=default_role.name)
        self.logger.info(f"User '{username}' created successfully with default role.")
        return user

    def delete_user(self, username: str) -> None:
        """
        Deletes a user from the system.

        :param username: The username of the user to delete.
        :raises UserNotFoundException: If the user does not exist.
        """
        self.logger.info(f"Deleting user: {username}")
        if user := self.get_user_by_username(username):
            user.delete_instance(recursive=True)
            self.logger.info(f"User '{username}' deleted successfully.")
            return

        self.logger.error(f"User '{username}' not found.")
        raise UserNotFoundException(username=username)

    def update_password(
        self, username: str, update_password_request: UpdateUserPasswordRequest
    ) -> UserDto:
        """
        Deletes a user from the system.

        :param username: The username of the user to update password.
        :param update_password_request: The old and new passwords to update.
        :raises UserNotFoundException: If the user does not exist.
        """

        if update_password_request.new_password == update_password_request.old_password:
            raise BadRequestException("passwords cannot match")

        if user := self.get_user_by_username(username=username):
            self.logger.info(f"found user for {username}")
            if not self.oauth_service.verify_password(
                plain_password=update_password_request.old_password,
                hashed_password=user.password_hash,
            ):
                self.logger.error(f"failed to validate password for user {username}")
                raise PermissionDeniedException(
                    detail=f"Invalid password for user {username}"
                )

            self.logger.info(f"updating password for user {username}")
            user.password_hash = self.oauth_service.get_password_hash(
                password=update_password_request.new_password
            )
            user.save()

            return UserDto.model_validate(user)

        self.logger.info(f"unable to fund user {username}")
        raise UserNotFoundException(username=username)

    def _validate_current_user(self, username: str, token: DecodedToken):
        if token.sub != username:
            self.logger.warning(
                f"user {token.sub} is attempting to update a user profile that is not theirs"
            )
            if token.is_admin:
                self.logger.info("user is admin, allowing profile update")
                return
            elif token.is_commissioner:
                self.logger.info("user is admin, allowing profile update")
                return
            raise PermissionDeniedException(
                detail=f"{token.sub} does not have permission to update {username}"
            )

    def update_user_profile(
        self, username: str, update_user_request: UpdateUserRequest, token: DecodedToken
    ) -> UserDto:
        """
        Get a user from by username.

        :param username: The username of the user to update.
        :param update_user_request: The updated user fields.
        :param token: Token used to validate permissions.
        :raises UserNotFoundException: If the user does not exist.
        """

        # validate that user is logged in or admin / commissioner
        self._validate_current_user(username=username, token=token)

        self.logger.info(f"Updating user: {username}")
        if user := self.get_user_by_username(username):
            self.logger.info(f"Found user '{username}'")

            user.username = update_user_request.username or user.username
            user.first_name = update_user_request.first_name or user.first_name
            user.last_name = update_user_request.last_name or user.last_name
            user.save()

            return UserDto.model_validate(user)

        self.logger.error(f"User '{username}' not found.")
        raise UserNotFoundException(username=username)

    def get_user(self, username: str) -> UserDto:
        """
        Get a user from by username.

        :param username: The username of the user to fetch.
        :raises UserNotFoundException: If the user does not exist.
        """
        self.logger.info(f"Fetching user: {username}")
        if user := self.get_user_by_username(username):
            self.logger.info(f"Found user '{username}'")
            roles = self.roles_service.get_roles_for_user(user=user)

            return UserDto(
                id=user.id,
                username=user.username,
                email=user.email,
                groups=roles,
            )

        self.logger.error(f"User '{username}' not found.")
        raise UserNotFoundException(username=username)

    def add_user_to_role(self, username: str, role_name: str) -> None:
        """
        Adds a user to a specific role.

        :param username: The username of the user to add to the role.
        :param role_name: The name of the role to assign to the user.
        """
        self.logger.info(f"Adding user '{username}' to role '{role_name}'")
        user = self.get_user_by_username(username)
        if not user:
            self.logger.error(f"User '{username}' not found.")
            raise UserNotFoundException(username=username)

        self.roles_service.manage_user_roles(username=username, role_name=role_name)
        self.logger.info(f"User '{username}' added to role '{role_name}' successfully.")
