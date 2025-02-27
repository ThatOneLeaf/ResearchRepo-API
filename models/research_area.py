from models import db
from models.base import BaseModel

class ResearchArea(BaseModel):
    __tablename__ = 'research_area'
    research_area_id = db.Column(db.String(6), primary_key=True, unique=True)
    research_area_name = db.Column(db.String(50))