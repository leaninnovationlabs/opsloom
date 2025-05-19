from uuid import UUID
from backend.api.account.models import Account, AccountCreate, AccountUpdate, AccountConfigResponse
from backend.lib.exceptions import AccountAlreadyExistsError, DatabaseError, AccountNotFoundError
import logging
from .repository import AccountRepository

logger = logging.getLogger(__name__)

class AccountService:
    __slots__ = ("repository",)
    def __init__(self, repository: AccountRepository):
        self.repository = repository

    async def create_account(self, acct_info: AccountCreate) -> Account:
        try:
            return await self.repository.create_account(acct_info)
        except (AccountAlreadyExistsError, DatabaseError) as e:
            logger.error(f"create_account error: {e}")
            raise

    async def get_account(self, account_id: UUID) -> Account:
        try:
            return await self.repository.get_account_by_id(account_id)
        except (AccountNotFoundError, DatabaseError) as e:
            logger.error(f"get_account error: {e}")
            raise

    async def validate_password(self, password: str) -> bool:
        try:
            return await self.repository.validate_password(password)
        except DatabaseError as e:
            logger.error(f"validate_password error: {e}")
            raise

    async def get_account_by_short_code(self, short_code: str) -> Account:
        try:
            return await self.repository.get_account_by_short_code(short_code)
        except (AccountNotFoundError, DatabaseError) as e:
            logger.error(f"get_account_by_short_code error: {e}")
            raise

    async def get_account_config_by_short_code(self, short_code: str) -> AccountConfigResponse:
        try:
            return await self.repository.get_account_config_by_short_code(short_code)
        except (AccountNotFoundError, DatabaseError) as e:
            logger.error(f"get_account_config_by_short_code error: {e}")
            raise

    async def get_root_account(self) -> Account:
        try:
            return await self.repository.get_root_account()
        except (AccountNotFoundError, DatabaseError) as e:
            logger.error(f"get_root_account error: {e}")
            raise

    async def get_account_by_email(self, email: str) -> Account:
        try:
            account = await self.repository.get_account_by_email(email)
            if not account:
                raise AccountNotFoundError(f"Account not found for email {email}")
            return account
        except (AccountNotFoundError, DatabaseError) as e:
            logger.error(f"get_account_by_email error: {e}")
            raise

    async def update_account(self, account_id: UUID, account_update: AccountUpdate) -> Account:
        try:
            account_update.account_id = account_id
            return await self.repository.update_account(account_update)
        except DatabaseError as e:
            logger.error(f"update_account error: {e}")
            raise