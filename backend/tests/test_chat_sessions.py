import pytest
from jobs.models import ChatMessage, ChatSession
from rest_framework.test import APIClient

from tests.factories import (
    ChatMessageFactory,
    ChatSessionFactory,
    CompanyFactory,
    JobFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def test_list_sessions_tenant_scoped(api_client):
    """
    Ensure sessions listed via GET /api/sessions/ are strictly tenant-scoped.
    """
    company_a = CompanyFactory()
    company_b = CompanyFactory()

    job_a = JobFactory(company=company_a)
    job_b = JobFactory(company=company_b)

    s1 = ChatSessionFactory(company=company_a, job=job_a)
    s2 = ChatSessionFactory(company=company_a, job=job_a)
    s3 = ChatSessionFactory(company=company_b, job=job_b)

    # Authenticate as Company A
    api_client.force_authenticate(user=company_a)
    response = api_client.get("/api/sessions/")
    assert response.status_code == 200

    results = (
        response.data["results"]
        if isinstance(response.data, dict)
        else response.data
    )
    returned_ids = [s["id"] for s in results]
    assert s1.id in returned_ids
    assert s2.id in returned_ids
    assert s3.id not in returned_ids

    # Authenticate as Company B
    api_client.force_authenticate(user=company_b)
    response_b = api_client.get("/api/sessions/")
    assert response_b.status_code == 200
    results_b = (
        response_b.data["results"]
        if isinstance(response_b.data, dict)
        else response_b.data
    )
    returned_ids_b = [s["id"] for s in results_b]
    assert returned_ids_b == [s3.id]


def test_list_sessions_filter_by_job(api_client):
    """
    Verify filtering sessions by job: GET /api/sessions/?job=<job_id>.
    """
    company = CompanyFactory()
    job_1 = JobFactory(company=company, title="Backend Engineer")
    job_2 = JobFactory(company=company, title="Frontend Engineer")

    s1 = ChatSessionFactory(company=company, job=job_1)
    s2 = ChatSessionFactory(company=company, job=job_1)
    s3 = ChatSessionFactory(company=company, job=job_2)

    api_client.force_authenticate(user=company)

    # Filter by job 1
    response = api_client.get(f"/api/sessions/?job={job_1.id}")
    assert response.status_code == 200
    results = (
        response.data["results"]
        if isinstance(response.data, dict)
        else response.data
    )
    returned_ids = [s["id"] for s in results]
    assert set(returned_ids) == {s1.id, s2.id}

    # Filter by job 2
    response_2 = api_client.get(f"/api/sessions/?job_id={job_2.id}")
    assert response_2.status_code == 200
    results_2 = (
        response_2.data["results"]
        if isinstance(response_2.data, dict)
        else response_2.data
    )
    assert [s["id"] for s in results_2] == [s3.id]


def test_create_session_success(api_client):
    """
    Verify creating a new chat session for a company's job: POST /api/sessions/.
    """
    company = CompanyFactory()
    job = JobFactory(company=company, title="Python Engineer")

    api_client.force_authenticate(user=company)
    response = api_client.post("/api/sessions/", {"job": job.id})

    assert response.status_code == 201
    assert response.data["job"] == job.id
    assert response.data["company"] == company.id
    assert response.data.get("job_title") == "Python Engineer"

    session_id = response.data["id"]
    session = ChatSession.objects.get(id=session_id)
    assert session.company == company
    assert session.job == job


def test_create_session_cross_tenant_forbidden(api_client):
    """
    Verify that Company A cannot create a chat session for Company B's job.
    """
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    job_b = JobFactory(company=company_b)

    api_client.force_authenticate(user=company_a)
    response = api_client.post("/api/sessions/", {"job": job_b.id})

    assert response.status_code == 400
    assert "job" in response.data


def test_retrieve_session_with_nested_messages(api_client):
    """
    Verify GET /api/sessions/<id>/ returns session details and nested messages.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    m1 = ChatMessageFactory(
        session=session, role=ChatMessage.Role.USER, content="Hello"
    )
    m2 = ChatMessageFactory(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content="How can I assist you today?",
    )

    api_client.force_authenticate(user=company)
    response = api_client.get(f"/api/sessions/{session.id}/")

    assert response.status_code == 200
    assert response.data["id"] == session.id
    assert len(response.data["messages"]) == 2
    assert response.data["messages"][0]["content"] == "Hello"
    assert response.data["messages"][1]["content"] == "How can I assist you today?"


def test_session_messages_subendpoint(api_client):
    """
    Verify GET /api/sessions/<id>/messages/ loads message history on session open.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    m1 = ChatMessageFactory(
        session=session, role=ChatMessage.Role.USER, content="Query 1"
    )
    m2 = ChatMessageFactory(
        session=session, role=ChatMessage.Role.ASSISTANT, content="Answer 1"
    )
    m3 = ChatMessageFactory(
        session=session, role=ChatMessage.Role.USER, content="Query 2"
    )

    api_client.force_authenticate(user=company)
    response = api_client.get(f"/api/sessions/{session.id}/messages/")

    assert response.status_code == 200
    results = (
        response.data["results"]
        if isinstance(response.data, dict)
        else response.data
    )
    assert len(results) == 3
    assert [m["content"] for m in results] == ["Query 1", "Answer 1", "Query 2"]


def test_cross_tenant_access_denied(api_client):
    """
    Verify Company B cannot access or mutate Company A's sessions.
    """
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    job_a = JobFactory(company=company_a)
    session_a = ChatSessionFactory(company=company_a, job=job_a)

    api_client.force_authenticate(user=company_b)

    # Retrieve
    get_res = api_client.get(f"/api/sessions/{session_a.id}/")
    assert get_res.status_code == 404

    # Messages sub-endpoint
    msg_res = api_client.get(f"/api/sessions/{session_a.id}/messages/")
    assert msg_res.status_code == 404

    # Delete
    del_res = api_client.delete(f"/api/sessions/{session_a.id}/")
    assert del_res.status_code == 404


def test_delete_session_success(api_client):
    """
    Verify a company can delete its own chat session.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    api_client.force_authenticate(user=company)
    response = api_client.delete(f"/api/sessions/{session.id}/")
    assert response.status_code == 204
    assert not ChatSession.objects.filter(id=session.id).exists()
