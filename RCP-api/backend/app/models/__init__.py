"""Import every model so SQLAlchemy's registry (and Alembic
autogenerate) sees all tables from a single import of `app.models`."""

from app.db.base import Base
from app.models.notification import Notification, NotificationType
from app.models.offer import OfferStatus, ResourceOffer
from app.models.request import HelpRequest, RequestStatus, UrgencyLevel
from app.models.resource import InventoryItem, InventoryStatus, ResourceCategory
from app.models.task import DispatchTask, TaskStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.volunteer import AvailabilityStatus, Skill, VolunteerProfile

__all__ = [
    "Base",
    "Tenant",
    "User",
    "UserRole",
    "VolunteerProfile",
    "Skill",
    "AvailabilityStatus",
    "ResourceCategory",
    "InventoryItem",
    "InventoryStatus",
    "HelpRequest",
    "RequestStatus",
    "UrgencyLevel",
    "ResourceOffer",
    "OfferStatus",
    "DispatchTask",
    "TaskStatus",
    "Notification",
    "NotificationType",
]
