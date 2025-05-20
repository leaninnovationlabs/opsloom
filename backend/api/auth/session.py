from backend.api.auth.models import User, UserCreate, LoggedInUser, UserLogin
from backend.api.account.services import AccountService
from backend.api.auth.repository import UserRepository
from backend.util.auth_utils import TokenData, create_access_token, PasswordService
from backend.util.log_setup import SetupLogging

logger = SetupLogging()

class UserManager:
    __slots__ = ("user_repository", "account_service", "password_service")
    def __init__(self, user_repository: UserRepository, account_service: AccountService):
        """
        :param user_repository: instance of UserRepository
        :param account_service: instance of AccountService
        """
        self.user_repository = user_repository
        self.account_service = account_service
        self.password_service = PasswordService()

    async def login_user(self, request: UserLogin):
        logger.info(f"Logging in user via email: {request.email}")
        
        if not request.email:
            logger.error("Email is required for email protected account")
            return None, "Email is required for email protected account", None

        if not request.password:
            logger.error("Password is required for email protected account")
            return None, "Password is required for email protected account", None

        # Lookup user by email
        user = await self.user_repository.get_user_by_email(request.email)
        if not user:
            logger.error(f"User not found: {request.email}")
            return None, "Invalid credentials", None

        # Check user’s account_short_code
        if user.account_short_code != request.account_short_code:
            logger.error(f"Mismatched short_code for user {request.email}: "
                         f"user={user.account_short_code} vs request={request.account_short_code}")
            return None, "Invalid credentials", None

        # Verify password
        if not self.password_service.verify_password(user.password, request.password):
            logger.error(f"Invalid password for user: {request.email}")
            return None, "Invalid credentials", None

        # Generate access token
        access_token = create_access_token(
            data=TokenData(
                email=user.email,
                account_id=str(user.account_id),
                account_short_code=user.account_short_code,
                user_id=str(user.id),
            )
        )
        loggedin_user = LoggedInUser(
            email=user.email,
            account_id=str(user.account_id),
            account_short_code=user.account_short_code,
            user_id=str(user.id)
        )
        return access_token, "Logged in successfully", loggedin_user

    async def signup_user(self, request: UserCreate):
        """
        Create a new user record and auto-login (return an access token).
        """
        # Validate account
        logger.info(f"\n\n\n\n\nUSER REQUEST:{request}\n\n\n\n\n")
        account = await self.account_service.get_account_by_short_code(request.account_shortcode)
        if not account:
            logger.error(f"Invalid account shortcode: {request.account_shortcode}")
            account = await self.account_service.get_root_account()

        # Check if user already exists
        existing_user = await self.user_repository.get_user_by_email(request.email)
        if request.email is None or existing_user is not None:
            logger.error(f"User already exists or no email provided: {request.email}")
            return None, "internal server error", None

        logger.info(f"Creating new user for account: {account.account_id} with protection={account.protection}")

        if account.protection == "email":
            # Additional checks for email-protected
            if not request.email:
                logger.error("Email is required for email protected account")
                return None, "Email is required for email protected account", None
            if not request.password:
                logger.error("Password is required for email protected account")
                return None, "Password is required for email protected account", None

            is_valid, error_message = self.password_service.validate_password_requirements(request.password)
            if not is_valid:
                logger.error(f"Password validation failed: {error_message}")
                return None, error_message, None

        elif account.protection == "none":
            # No password needed
            logger.info("Creating user for unprotected account")
            request.email = None

        # Hash password if present
        hashed_password = None
        if request.password:
            hashed_password = self.password_service.hash_password(request.password)

        # Build user object
        new_user = User(
            email=request.email,
            account_id=account.account_id,
            account_short_code=account.short_code,
            password=hashed_password,
            phone_no=request.phone_no
        )
        # Create user in DB
        created_user = await self.user_repository.create_user(new_user)
        if not created_user:
            logger.error("Failed to create user in DB")
            return None, "Failed to create user", None

        # Generate token
        access_token = create_access_token(
            data=TokenData(
                email=created_user.email,
                account_id=str(account.account_id),
                account_short_code=account.short_code,
                user_id=str(created_user.id),
            )
        )
        loggedin_user = LoggedInUser(
            email=created_user.email,
            account_id=str(account.account_id),
            account_short_code=account.short_code,
            user_id=str(created_user.id)
        )

        logger.info(f"User {created_user.email} created and logged in.")
        return access_token, "Account created and logged in successfully", loggedin_user
