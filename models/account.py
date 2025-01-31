from models import db
from models.base import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import relationship
from .user_profile import UserProfile

class Account(BaseModel):
    __tablename__ = 'account'
    user_id = db.Column(db.String(15), primary_key=True, unique=True)
    email = db.Column(db.String(80))
    user_pw = db.Column(db.String(256))
    acc_status = db.Column(db.String(20), server_default=text("'ACTIVATED'"))
    role_id = db.Column(db.String(2), db.ForeignKey('roles.role_id'))
    role = db.relationship('Role', backref=db.backref('accounts', lazy=True))

    # Define a relationship to UserProfile
    user_profile = relationship('UserProfile', backref='account', uselist=False, primaryjoin="Account.user_id == UserProfile.researcher_id")

    def __repr__(self):
        return f"<Account {self.user_id}>"
