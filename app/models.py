from datetime import datetime, timezone
from app import db

class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(255))
    event_type = db.Column(db.String(50))
    source_url = db.Column(db.String(500))
    source_name = db.Column(db.String(100))
    parsed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'external_id': self.external_id,
            'title': self.title,
            'description': self.description,
            'event_date': self.event_date.strftime('%Y-%m-%d %H:%M:%S') if self.event_date else None,
            'location': self.location,
            'event_type': self.event_type,
            'source_url': self.source_url,
            'source_name': self.source_name,
            'parsed_at': self.parsed_at.isoformat() if self.parsed_at else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }