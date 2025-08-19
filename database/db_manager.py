# facebook_business_bot/database/db_manager.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import date, timedelta

from config import DATABASE_URL
from database.models import Base, User
from services.tempmail_api import tempmail_api # Import tempmail_api instance

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
            print("Database tables created or already exist.")
        except SQLAlchemyError as e:
            print(f"Error creating tables: {e}")
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
                print(f"User {telegram_id} already exists.")
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
            print(f"User {telegram_id} added successfully.")
            return new_user
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error adding user {telegram_id}: {e}")
            raise
        finally:
            session.close()

    def get_user(self, telegram_id: int) -> User:
        """Retrieves a user by their Telegram ID."""
        session = self.get_session()
        try:
            return session.query(User).filter_by(telegram_id=telegram_id).first()
        except SQLAlchemyError as e:
            print(f"Error getting user {telegram_id}: {e}")
            raise
        finally:
            session.close()

    def update_user(self, user: User) -> bool:
        """Updates an existing user's information."""
        session = self.get_session()
        try:
            session.merge(user) # Use merge for updating detached objects
            session.commit()
            print(f"User {user.telegram_id} updated successfully.")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error updating user {user.telegram_id}: {e}")
            raise
        finally:
            session.close()

    def delete_user(self, telegram_id: int) -> bool:
        """Deletes a user by their Telegram ID."""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                session.delete(user)
                session.commit()
                print(f"User {telegram_id} deleted successfully.")
                return True
            print(f"User {telegram_id} not found for deletion.")
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error deleting user {telegram_id}: {e}")
            raise
        finally:
            session.close()

    def get_all_users(self) -> list[User]:
        """Retrieves all users from the database."""
        session = self.get_session()
        try:
            return session.query(User).all()
        except SQLAlchemyError as e:
            print(f"Error getting all users: {e}")
            raise
        finally:
            session.close()

    def is_user_subscribed(self, user: User) -> bool:
        """Checks if a user's subscription is active."""
        if not user or not user.subscription_end_date:
            return False
        return user.subscription_end_date >= date.today()

    def renew_subscription(self, telegram_id: int, days: int) -> bool:
        """Renews a user's subscription by adding days."""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                print(f"User {telegram_id} not found for renewal.")
                return False

            current_end_date = user.subscription_end_date if user.subscription_end_date and user.subscription_end_date >= date.today() else date.today()
            user.subscription_end_date = current_end_date + timedelta(days=days)
            session.commit()
            print(f"Subscription for user {telegram_id} renewed for {days} days. New end date: {user.subscription_end_date}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error renewing subscription for user {telegram_id}: {e}")
            raise
        finally:
            session.close()

    def reward_all_users(self, days: int) -> int:
        """Rewards all users by adding days to their subscription."""
        session = self.get_session()
        updated_count = 0
        try:
            users = session.query(User).all()
            for user in users:
                current_end_date = user.subscription_end_date if user.subscription_end_date and user.subscription_end_date >= date.today() else date.today()
                user.subscription_end_date = current_end_date + timedelta(days=days)
                updated_count += 1
            session.commit()
            print(f"Rewarded {updated_count} users with {days} days.")
            return updated_count
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error rewarding all users: {e}")
            raise
        finally:
            session.close()

    async def get_or_create_daily_temp_email(self, user_id: int, api_key: str) -> str:
        """
        Retrieves the user's daily temporary email address.
        Creates a new one if it's a new day or no email is stored.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found in database.")

            today = date.today()

            # Check if we already have an email for today
            if user.last_email_creation_date == today and user.current_temp_email_address:
                print(f"Using existing daily email for user {user_id}: {user.current_temp_email_address}")
                return user.current_temp_email_address
            
            # If not, create a new one
            print(f"Creating new daily email for user {user_id}...")
            new_email = tempmail_api.create_temp_email(api_key)
            if not new_email:
                raise Exception("Failed to create new temporary email.")

            user.last_email_creation_date = today
            user.current_temp_email_address = new_email
            session.commit()
            print(f"New daily email created and saved for user {user_id}: {new_email}")
            return new_email

        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error managing daily temp email for user {user_id}: {e}")
            raise
        except Exception as e:
            print(f"Error in get_or_create_daily_temp_email for user {user_id}: {e}")
            raise
        finally:
            session.close()

# Initialize DBManager globally or pass it around
db_manager = DBManager()

