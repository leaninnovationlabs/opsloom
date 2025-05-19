from uuid import UUID, uuid4
from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from backend.api.account.account_schema import AccountORM
from backend.api.account.models import (
    Account,
    AccountCreate,
    AccountUpdate,
    AccountConfigResponse
)
from backend.lib.exceptions import (
    AccountAlreadyExistsError,
    DatabaseError,
    AccountNotFoundError
)

logger = logging.getLogger(__name__)

class AccountRepository:
    """
    A repository responsible for all direct DB operations regarding Accounts.
    """
    __slots__ = ("session",)
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_account(self, account_create: AccountCreate) -> Account:
        """
        Insert an account row into the DB from Pydantic input model.
        """
        new_account = AccountORM(
            account_id=uuid4(),
            short_code=account_create.short_code,
            name=account_create.name,
            email=account_create.email,
            account_metadata=account_create.metadata,
            protection=account_create.protection,
            root=False
        )

        self.session.add(new_account)
        try:
            await self.session.commit()
            await self.session.refresh(new_account)
        except IntegrityError as e:
            await self.session.rollback()
            # Unique constraint violation checks
            msg = str(e.orig).lower() if e.orig else ""
            if "account_short_code_key" in msg:
                raise AccountAlreadyExistsError(f"Account with short_code '{account_create.short_code}' already exists.")
            elif "account_email_key" in msg:
                raise AccountAlreadyExistsError(f"Account with email '{account_create.email}' already exists.")
            else:
                raise DatabaseError("An integrity error occurred in the database.")
        except Exception:
            await self.session.rollback()
            raise DatabaseError("A database error occurred while creating an account.")

        # Convert the ORM object to a Pydantic model
        return Account.model_validate(new_account)

    async def get_account_by_id(self, account_id: UUID) -> Account:
        """
        Retrieve an account by its ID.
        """
        stmt = select(AccountORM).where(AccountORM.account_id == account_id)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()

        if not account_orm:
            raise AccountNotFoundError("Account not found.")

        return Account.model_validate(account_orm)

    async def get_account_by_short_code(self, short_code: str) -> Account:
        stmt = select(AccountORM).where(AccountORM.short_code == short_code)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()

        if not account_orm:
            raise AccountNotFoundError("Account not found.")
        return Account.model_validate(account_orm)

    async def get_account_config_by_short_code(self, short_code: str) -> AccountConfigResponse:
        stmt = select(AccountORM).where(AccountORM.short_code == short_code)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()

        if not account_orm:
            raise AccountNotFoundError("Account not found.")

        return AccountConfigResponse.model_validate(account_orm)

    async def get_root_account(self) -> Account:
        stmt = select(AccountORM).where(AccountORM.root)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()

        if not account_orm:
            raise AccountNotFoundError("Root account not found.")

        return Account.model_validate(account_orm)

    async def get_account_by_email(self, email: str) -> Optional[Account]:
        stmt = select(AccountORM).where(AccountORM.email == email)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()
        if not account_orm:
            return None
        return Account.model_validate(account_orm)

    async def verify_email(self, email: str) -> bool:
        stmt = select(AccountORM).where(AccountORM.email == email)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()
        return account_orm is not None

    async def validate_password(self, password: str) -> bool:
        """
        Example method if you have a password column for demonstration only.
        Adjust accordingly if your schema is different.
        """
        stmt = select(AccountORM).where(AccountORM.protection == password)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()
        return account_orm is not None

    async def update_account(self, account_update: AccountUpdate) -> Account:
        """
        Update an existing account from Pydantic input model.
        """
        if not account_update.account_id:
            raise ValueError("AccountUpdate requires an 'id' to update.")

        # Generate update data excluding unset fields and account_id
        update_data = account_update.model_dump(exclude_unset=True, exclude={"account_id"})

        stmt = (
            update(AccountORM)
            .where(AccountORM.account_id == account_update.account_id)
            .values(**update_data)
            .returning(AccountORM)
        )

        try:
            result = await self.session.execute(stmt)
            await self.session.commit()
            updated_orm = result.scalar_one_or_none()
            if not updated_orm:
                raise AccountNotFoundError("Account not found for update.")
            return Account.model_validate(updated_orm)
        except IntegrityError as e:
            await self.session.rollback()
            # Handle unique constraint violations
            msg = str(e.orig).lower() if e.orig else ""
            if "account_short_code_key" in msg:
                raise AccountAlreadyExistsError(f"Short code '{account_update.short_code}' already exists.")
            elif "account_email_key" in msg:
                raise AccountAlreadyExistsError(f"Email '{account_update.email}' already exists.")
            else:
                raise DatabaseError("An integrity error occurred while updating account.")
        except Exception:
            await self.session.rollback()
            raise DatabaseError("A database error occurred while updating account.")

    async def delete_account(self, account_id: UUID) -> bool:
        """
        Delete an account by its ID.
        """
        stmt = select(AccountORM).where(AccountORM.account_id == account_id)
        result = await self.session.execute(stmt)
        account_orm = result.scalar_one_or_none()
        
        if not account_orm:
            raise AccountNotFoundError("Account not found for deletion.")
        
        await self.session.delete(account_orm)
        await self.session.flush() 
        await self.session.commit()  
        return True
        
    
