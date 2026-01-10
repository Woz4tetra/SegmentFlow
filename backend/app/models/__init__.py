"""Database models module.

Importing models here ensures SQLAlchemy registers all mapped classes when
``app.core.database.init_db`` runs ``Base.metadata.create_all``.
"""

from app.models.image import Image, ImageStatus, ValidationStatus
from app.models.label import Label
from app.models.labeled_point import LabeledPoint
from app.models.mask import Mask
from app.models.project import Project, ProjectStage
from app.models.stats import Stats
from app.models.user_settings import Theme, UserSettings

__all__ = [
	"Image",
	"ImageStatus",
	"ValidationStatus",
	"Label",
	"LabeledPoint",
	"Mask",
	"Project",
	"ProjectStage",
	"Stats",
	"Theme",
	"UserSettings",
]
