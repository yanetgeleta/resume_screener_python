import json

import pytest
from applicants.auth import generate_applicant_tokens
from applicants.models import Applicant
from django.core.files.uploadedfile import SimpleUploadedFile
from jobs.models import Application, ApplicationAnswer, ChatSession, Job
from jobs.services.chat import format_ranked_candidates_context
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import (
    ApplicantFactory,
    ApplicationFactory,
    CompanyFactory,
    JobApplicationFieldFactory,
    JobFactory,
    ResumeFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestApplicantAuth:
    def test_applicant_signup_and_jwt_issuance(self, api_client):
        signup_data = {
            "email": "candidate@example.com",
            "full_name": "Jane Candidate",
            "phone_number": "+1234567890",
            "password": "StrongPassword123!",
        }
        response = api_client.post(
            "/api/applicants/signup/", signup_data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "tokens" in data
        assert "access" in data["tokens"]
        assert "refresh" in data["tokens"]
        assert data["applicant"]["email"] == "candidate@example.com"
        assert data["applicant"]["full_name"] == "Jane Candidate"

        # Verify applicant is in DB and password was hashed
        applicant = Applicant.objects.get(email="candidate@example.com")
        assert applicant.check_password("StrongPassword123!")
        assert applicant.password != "StrongPassword123!"

    def test_applicant_login_and_profile_access(self, api_client):
        applicant = ApplicantFactory(
            email="login_user@example.com", password="SecurePassword123!"
        )
        login_data = {
            "email": "login_user@example.com",
            "password": "SecurePassword123!",
        }
        response = api_client.post("/api/applicants/login/", login_data, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        access_token = data["tokens"]["access"]

        # Access profile /api/applicants/me/
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_response = api_client.get("/api/applicants/me/")
        assert me_response.status_code == status.HTTP_200_OK
        assert me_response.json()["email"] == "login_user@example.com"

    def test_guest_application_associated_on_signup(self, api_client):
        job = JobFactory()
        resume = ResumeFactory(applicant=None)
        guest_app = ApplicationFactory(
            job=job,
            resume=resume,
            applicant=None,
            guest_email="guest.user@example.com",
            guest_full_name="Guest User",
            guest_phone_number="+1987654321",
        )

        signup_data = {
            "email": "guest.user@example.com",
            "full_name": "Guest User",
            "phone_number": "+1987654321",
            "password": "StrongPassword123!",
        }
        response = api_client.post(
            "/api/applicants/signup/", signup_data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED

        applicant = Applicant.objects.get(email="guest.user@example.com")
        guest_app.refresh_from_db()
        resume.refresh_from_db()

        assert guest_app.applicant == applicant
        assert resume.applicant == applicant

        # Verify applicant can now see the application via /api/applicants/me/applications/
        access_token = response.json()["tokens"]["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        apps_response = api_client.get("/api/applicants/me/applications/")
        assert apps_response.status_code == status.HTTP_200_OK
        apps_data = apps_response.json()
        assert len(apps_data) == 1
        assert apps_data[0]["id"] == guest_app.id


@pytest.mark.django_db
class TestJobApplicationFieldsAndSearch:
    def test_create_job_with_dynamic_application_fields(self, api_client):
        company = CompanyFactory()
        api_client.force_authenticate(user=company)

        job_payload = {
            "title": "Full Stack Engineer",
            "description": "Looking for Python and React specialist.",
            "head_count": 2,
            "application_fields": [
                {
                    "label": "GitHub Profile URL",
                    "field_type": "text",
                    "required": True,
                    "order": 0,
                },
                {
                    "label": "Work Authorization",
                    "field_type": "single_choice",
                    "choices": ["Citizen", "Green Card", "Visa Required"],
                    "required": True,
                    "order": 1,
                },
            ],
        }

        response = api_client.post("/api/jobs/", job_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        job_data = response.json()
        assert job_data["title"] == "Full Stack Engineer"
        assert len(job_data["application_fields"]) == 2

        job = Job.objects.get(id=job_data["id"])
        fields = job.application_fields.all()
        assert fields.count() == 2
        assert fields.filter(
            label="GitHub Profile URL", field_type="text", required=True
        ).exists()
        assert fields.filter(
            label="Work Authorization", field_type="single_choice"
        ).exists()

    def test_job_search_public(self, api_client, mocker):
        mocker.patch("jobs.views.embed_text", return_value=[0.1] * 384)
        company = CompanyFactory()
        JobFactory(
            company=company,
            title="Lead Python Django Developer",
            description="Backend APIs",
            is_active=True,
        )
        JobFactory(
            company=company,
            title="Marketing Specialist",
            description="SEO & Social Media",
            is_active=True,
        )

        # Public search without authentication
        response = api_client.get("/api/jobs/search/?q=Django")
        assert response.status_code == status.HTTP_200_OK
        results = response.json()
        assert len(results) >= 1
        assert "Django" in results[0]["title"]


@pytest.mark.django_db
class TestJobApplyFlow:
    def test_apply_as_authenticated_applicant_with_custom_answers(self, api_client):
        company = CompanyFactory()
        job = JobFactory(company=company, is_active=True)
        field1 = JobApplicationFieldFactory(
            job=job, label="Portfolio Link", field_type="text", required=True
        )
        applicant = ApplicantFactory(email="dev@example.com")
        tokens = generate_applicant_tokens(applicant)

        pdf_file = SimpleUploadedFile(
            "resume.pdf", b"%PDF-1.4 dummy pdf content", content_type="application/pdf"
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        answers = json.dumps(
            [{"field_id": field1.id, "value": "https://github.com/developer"}]
        )
        payload = {
            "file": pdf_file,
            "answers": answers,
        }

        response = api_client.post(
            f"/api/jobs/{job.id}/apply/", payload, format="multipart"
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "submitted"
        assert data["pipeline_status"] == "pending"

        # Verify application in database
        application = Application.objects.get(id=data["application_id"])
        assert application.job == job
        assert application.applicant == applicant
        assert application.source == Application.Source.APPLICANT_SUBMITTED
        assert application.answers.count() == 1
        assert application.answers.first().value == "https://github.com/developer"

    def test_apply_as_guest_applicant(self, api_client):
        company = CompanyFactory()
        job = JobFactory(company=company, is_active=True)
        pdf_file = SimpleUploadedFile(
            "guest_resume.pdf",
            b"%PDF-1.4 dummy pdf content",
            content_type="application/pdf",
        )

        payload = {
            "full_name": "Guest Candidate",
            "email": "guest@example.com",
            "phone_number": "+1987654321",
            "file": pdf_file,
        }

        response = api_client.post(
            f"/api/jobs/{job.id}/apply/", payload, format="multipart"
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "submitted"

        app = Application.objects.get(id=data["application_id"])
        assert app.applicant is None
        assert app.guest_full_name == "Guest Candidate"
        assert app.guest_email == "guest@gmail.com"
        assert app.guest_phone_number == "+251923456789"
        assert app.source == Application.Source.APPLICANT_SUBMITTED


@pytest.mark.django_db
class TestSeeResultAndContactPrompt:
    def test_see_result_endpoint_validation_and_session_creation(self, api_client):
        company = CompanyFactory()
        job = JobFactory(company=company)
        api_client.force_authenticate(user=company)

        # 1. No processed applications yet -> 400 Bad Request
        res_before = api_client.post(f"/api/jobs/{job.id}/see-result/")
        assert res_before.status_code == status.HTTP_400_BAD_REQUEST

        # 2. Add an application with pipeline_status = processed
        resume = ResumeFactory(company=company)
        ApplicationFactory(
            job=job,
            resume=resume,
            pipeline_status=Application.PipelineStatus.PROCESSED,
            final_score=85.0,
        )

        res_after = api_client.post(f"/api/jobs/{job.id}/see-result/")
        assert res_after.status_code == status.HTTP_200_OK
        data = res_after.json()
        assert "session_id" in data
        assert ChatSession.objects.filter(
            id=data["session_id"], job=job, company=company
        ).exists()

    def test_candidate_context_includes_contact_and_personal_details(self):
        applicant = ApplicantFactory(
            full_name="Alex Rivera",
            email="alex.rivera@example.com",
            phone_number="+251923456789",
        )
        resume = ResumeFactory(
            original_filename="alex_rivera_cv.pdf",
            full_text="Alex Rivera | Software Engineer\nEmail: alex.rivera@example.com\nGitHub: github.com/arivera\nLinkedIn: linkedin.com/in/arivera\nSkills: Python, Django",
            skills=["Python", "Django"],
            experience_years=5,
        )
        job = JobFactory()
        field = JobApplicationFieldFactory(
            job=job, label="Portfolio Link", field_type="text"
        )

        app = ApplicationFactory(
            job=job,
            resume=resume,
            applicant=applicant,
            final_score=92.5,
            retrieval_score=-0.85,
            pipeline_status=Application.PipelineStatus.PROCESSED,
        )
        ApplicationAnswer.objects.create(
            application=app, field=field, value="https://alexrivera.dev"
        )

        context = format_ranked_candidates_context([app])

        # Assert contact information is explicitly embedded in LLM context
        assert "Alex Rivera" in context
        assert "alex.rivera@example.com" in context
        assert "+1-555-987-6543" in context
        assert "github.com/arivera" in context
        assert "linkedin.com/in/arivera" in context
        assert "Portfolio Link: https://alexrivera.dev" in context
