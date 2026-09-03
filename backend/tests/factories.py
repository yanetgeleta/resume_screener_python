import factory
from accounts.models import Company
from factory.faker import Faker
from jobs.models import Application, Job, Resume, ResumeChunk


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta(factory.django.DjangoModelFactory.Meta):
        model = Company

    email = Faker("email")
    company_name = Faker("company")
    password = "password123"
    is_active = True
    is_staff = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Ensure password hashing is run via create_user manager"""
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, **kwargs)


# ---------------------------------------------------------------------------
# Job Factories
# ---------------------------------------------------------------------------
class JobFactory(factory.django.DjangoModelFactory):
    class Meta(factory.django.DjangoModelFactory.Meta):
        model = Job

    company = factory.SubFactory(CompanyFactory)
    title = Faker("job")
    description = Faker("paragraph")
    required_experience_years = Faker("pyint", min_value=1, max_value=10)
    skills = ["python", "django", "postgresql"]
    head_count = 5
    ranking_status = Job.RankingStatus.NOT_STARTED
    is_active = True


class NoneSkillsJobFactory(JobFactory):
    """Pre-extraction state: no skills and no required experience years"""

    skills = None
    required_experience_years = None


class SkillsJobFactory(JobFactory):
    """Post-extraction state: explicit skills and experience years"""

    skills = ["python", "django", "docker", "fastapi"]
    required_experience_years = 3


# ---------------------------------------------------------------------------
# Resume Factories
# ---------------------------------------------------------------------------
class ResumeFactory(factory.django.DjangoModelFactory):
    class Meta(factory.django.DjangoModelFactory.Meta):
        model = Resume

    company = factory.SubFactory(CompanyFactory)
    original_filename = "resume.pdf"
    file = factory.django.FileField(filename="resume.pdf", data=b"%PDF-1.4 dummy pdf")
    full_text = Faker("text")
    skills = ["python", "django"]
    experience_years = 4
    status = Resume.Status.DONE


class NoneSkillsResumeFactory(ResumeFactory):
    """Pre-extraction state: uploaded but not parsed yet"""

    skills = None
    experience_years = None
    status = Resume.Status.PENDING


class SkillsResumeFactory(ResumeFactory):
    """Post-extraction state: parsed with skills and years"""

    skills = ["python", "django", "postgresql", "celery"]
    experience_years = 5
    status = Resume.Status.DONE


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------
class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta(factory.django.DjangoModelFactory.Meta):
        model = Application

    job = factory.SubFactory(JobFactory)

    # SelfAttribute('..job.company') guarantees the Resume and Job
    # belong to the SAME Company/Tenant by default!
    resume = factory.SubFactory(
        ResumeFactory,
        company=factory.SelfAttribute("..job.company"),
    )
    status = Application.Status.NORMAL
    retrieval_score = None
    final_score = None
    llm_profile = None


# ---------------------------------------------------------------------------
# Resume Chunk Factory (for vector search tests)
# ---------------------------------------------------------------------------
class ResumeChunkFactory(factory.django.DjangoModelFactory):
    class Meta(factory.django.DjangoModelFactory.Meta):
        model = ResumeChunk

    resume = factory.SubFactory(ResumeFactory)
    chunk_text = Faker("paragraph")
    embedding = [0.01] * 384  # 384-dimensional dummy normalized vector
    chunk_index = factory.Sequence(lambda n: n)
