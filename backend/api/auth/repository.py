from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from sqlalchemy import select, update
from sqlalchemy.sql import func

from backend.api.auth.user_schema import UserORM
from backend.api.auth.models import User
import logging

logger = logging.getLogger(__name__)

class UserRepository:
    """
    Repository for CRUD operations on the 'users' table.
    """
    __slots__ = ("session",)
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, new_user: User) -> Optional[User]:
        """
        Insert a new user row using the Pydantic 'User' model.
        """
        try:
            logger.info(f"\n\nUSER: {new_user}\n\n")
            orm_user = UserORM(
                id=new_user.id,
                account_id=new_user.account_id,
                account_short_code=new_user.account_short_code,
                email=new_user.email,
                password=new_user.password,
                phone_no=new_user.phone_no,
                active=new_user.active,
            )
            self.session.add(orm_user)
            await self.session.commit()
            await self.session.refresh(orm_user)
            logger.info(f"User created: {self._to_pydantic(orm_user)}")
            return self._to_pydantic(orm_user)
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"create_user: SQLAlchemy Error: {str(e)}")
            return None

    async def validate_password(self, password: str) -> bool:
        """
        Check if there's at least one user with the given password. 
        (This method is questionable for real security, but we'll keep it for backward compatibility.)
        """
        try:
            stmt = select(UserORM).where(UserORM.password == password)
            result = await self.session.execute(stmt)
            user_orm = result.scalar_one_or_none()
            return user_orm is not None
        except NoResultFound:
            logger.error("Invalid password!")
            return False
        except SQLAlchemyError as e:
            logger.error(f"validate_password: {str(e)}")
            return False

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Return a single user row that matches the given email.
        """
        try:
            stmt = select(UserORM).where(UserORM.email == email)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.error(f"No user found for email: {email}")
                return None
            return self._to_pydantic(orm_obj)
        except SQLAlchemyError as e:
            logger.error(f"get_user_by_email: SQLAlchemy Error: {str(e)}")
            return None

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Return a single user row that matches the given user_id.
        """
        try:
            stmt = select(UserORM).where(UserORM.id == user_id)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.error(f"No user found for user_id: {user_id}")
                return None
            return self._to_pydantic(orm_obj)
        except SQLAlchemyError as e:
            logger.error(f"get_user_by_user_id: {str(e)}")
            return None

    async def update_user(self, user: User) -> Optional[User]:
        """
        Update the user row with new info from the Pydantic 'User' model.
        """
        try:
            # We only update certain fields
            stmt = (
                update(UserORM)
                .where(UserORM.id == user.id)
                .values(
                    email=user.email,
                    password=user.password,
                    phone_no=user.phone_no,
                    active=user.active,
                    updated_at=func.now()
                )
                .returning(UserORM)
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            updated_orm = result.scalar_one_or_none()
            if not updated_orm:
                logger.error(f"No user found with ID: {user.id}")
                return None
            return self._to_pydantic(updated_orm)
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"update_user: {str(e)}")
            return None
    
    async def delete_user(self, user_id: UUID) -> bool:
        """
        Delete the user row with the given user_id.
        """
        try:
            stmt = select(UserORM).where(UserORM.id == user_id)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.error(f"No user found with ID: {user_id}")
                return False
            self.session.delete(orm_obj)

            await self.session.commit()
            return True
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"delete_user: {str(e)}")
            return False


    def _to_pydantic(self, orm_obj: UserORM) -> User:
        """
        Convert the SQLAlchemy ORM object to a Pydantic 'User' model.
        """
        return User(
            id=orm_obj.id,
            account_id=orm_obj.account_id,
            account_short_code=orm_obj.account_short_code,
            password=orm_obj.password,
            phone_no=orm_obj.phone_no,
            active=orm_obj.active,
            created_at=orm_obj.created_at,
            email=orm_obj.email,
        )
