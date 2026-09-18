from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
    ) -> User:
        user = User(email=email, hashed_password=hashed_password, full_name=full_name)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_email(self, email: str) -> User | None:
        query = select(User).where(User.email == email)
        result = await self._session.execute(query)
        return result.scalars().first()

    async def get_by_id(self, user_id: UUID) -> User | None:
        query = select(User).where(User.id == user_id)
        result = await self._session.execute(query)
        return result.scalars().first()

    async def mark_email_verified(self, user: User) -> None:
        user.is_email_verified = True
        await self._session.flush()

    async def update_password(self, user: User, hashed_password: str) -> None:
        user.hashed_password = hashed_password
        await self._session.flush()

    async def update_profile(self, user: User, full_name: str | None, avatar_url: str | None) -> None:
        user.full_name = full_name
        user.avatar_url = avatar_url
        await self._session.flush()

    async def set_active(self, user: User, is_active: bool) -> None:
        user.is_active = is_active
        await self._session.flush()

    async def set_platform_admin(self, user: User, is_platform_admin: bool) -> None:
        user.is_platform_admin = is_platform_admin
        await self._session.flush()
