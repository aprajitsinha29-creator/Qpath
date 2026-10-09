"""SQLAlchemy ORM models, one file per aggregate (AGENTS.md 3.3.4).

Importing this package registers every model on ``Base.metadata`` before
``create_all`` runs (see ``app.db.session.init_db``).
"""

from app.models.career_path import CareerPath
from app.models.concept import Concept
from app.models.job_posting import JobPosting, JobPostingSkill, JobPostingSubfield
from app.models.path_explanation import PathExplanation
from app.models.profile import Assessment, Profile
from app.models.pulse_snapshot import PulseSnapshot
from app.models.quiz import Question
from app.models.refresh_run import RefreshRun
from app.models.research import PaperSnapshot, ResearchTheme
from app.models.serpapi_call_log import SerpApiCallLog
from app.models.skill import Skill
from app.models.subfield import Subfield

__all__ = [
    "Assessment",
    "CareerPath",
    "Concept",
    "JobPosting",
    "JobPostingSkill",
    "JobPostingSubfield",
    "PaperSnapshot",
    "PathExplanation",
    "Profile",
    "PulseSnapshot",
    "Question",
    "RefreshRun",
    "ResearchTheme",
    "SerpApiCallLog",
    "Skill",
    "Subfield",
]
