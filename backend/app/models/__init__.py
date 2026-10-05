"""SQLAlchemy ORM models, one file per aggregate (AGENTS.md 3.3.4).

Importing this package registers every model on ``Base.metadata`` before
``create_all`` runs (see ``app.db.session.init_db``).
"""

from app.models.career_path import CareerPath
from app.models.concept import Concept
from app.models.job_posting import JobPosting, JobPostingSubfield
from app.models.pulse_snapshot import PulseSnapshot
from app.models.refresh_run import RefreshRun
from app.models.serpapi_call_log import SerpApiCallLog
from app.models.skill import Skill
from app.models.subfield import Subfield

__all__ = [
    "CareerPath",
    "Concept",
    "JobPosting",
    "JobPostingSubfield",
    "PulseSnapshot",
    "RefreshRun",
    "SerpApiCallLog",
    "Skill",
    "Subfield",
]
