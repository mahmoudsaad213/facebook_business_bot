# facebook_business_bot/database/db_manager.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import date, timedelta
import logging

from config import DATABASE_URL
from database.models import Base, User

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self):
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL is not configured.")
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        self.create_tables()

    def create_tables(self):
        """Creates database tables if they don't exist."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created or already exist.")
        except SQLAlchemyError as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def get_session(self):
        """Returns a new session."""
        return self.Session()

    def add_user(self, telegram_id: int, is_admin: bool = False, tempmail_api_key: str = None, subscription_days: int = 0) -> User:
        """Adds a new user to the database."""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                logger.info(f"User  {telegram_id} already exists.")
                return user

            subscription_end_date = None
            if subscription_days > 0:
                subscription_end_date = date.today() + timedelta(days=subscription_days)

            new_user = User(
                telegram_id=telegram_id,
                is_admin=is_admin,
                tempmail_api_key=tempmail_api_key,
                subscription_end_date=subscription_end_date
            )
            session.add(new_user)
            session.commit()
            logger.info(f"User  {telegram_id} added successfully.")
            return new_user
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error adding user {telegram_id}: {e}")
            raise
        finally:
            session.close()

    def get_user(self, telegram_id: int) -> User:
        """Retrieves a user by their Telegram ID."""
        session = self.get_session()
        try:
            return session.query(User).filter_by(telegram_id=telegram_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user {telegram_id}: {e}")
            raise
        finally:
            session.close()

    def update_user(self, user: User) -> bool:
        """Updates an existing user's information."""
        session = self.get_session()
        try:
            session.merge(user)
            session.commit()
            logger.info(f"User  {user.telegram_id} updated successfully.")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating user {user.telegram_id}: {e}")
            raise
        finally:
            session.close()

    def delete_user(self, telegram_id: int) -> bool:
        """Deletes a user by their Telegram ID."""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if
