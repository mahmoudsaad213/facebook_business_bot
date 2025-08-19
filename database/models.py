# facebook_business_bot/database/models.py
from sqlalchemy import Column, BigInteger, String, Boolean, Date, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True, unique=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    tempmail_api_key = Column(String, nullable=True)
    subscription_end_date = Column(Date, nullable=True)
    last_email_creation_date = Column(Date, nullable=True)
    current_temp_email_address = Column(String, nullable=True)
    businesses_created_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (f"<User(telegram_id={self.telegram_id}, is_admin={self.is_admin}, "
                f"subscription_end_date={self.subscription_end_date}, "
                f"businesses_created_count={self.businesses_created_count})>")
