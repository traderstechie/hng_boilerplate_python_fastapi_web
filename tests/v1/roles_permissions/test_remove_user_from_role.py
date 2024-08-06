import pytest
from uuid_extensions import uuid7
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app
from api.db.database import get_db
from api.v1.models import User, Organization
from api.v1.services.user import user_service
from api.v1.models.permissions.role import Role
from api.v1.models.permissions.user_org_role import user_organization_roles

client = TestClient(app)

# Mock database
@pytest.fixture
def mock_db_session(mocker):
    db_session_mock = mocker.MagicMock(spec=Session)
    app.dependency_overrides[get_db] = lambda: db_session_mock
    return db_session_mock

@pytest.fixture
def mock_user_service():
    with patch("api.v1.services.user.user_service", autospec=True) as user_service_mock:
        yield user_service_mock

@pytest.fixture
def mock_org_service():
    with patch("api.v1.services.organization.organization_service", autospec=True) as org_service_mock:
        yield org_service_mock

@pytest.fixture
def mock_role_service():
    with patch("api.v1.services.permissions.role_service.role_service", autospec=True) as role_service_mock:
        yield role_service_mock

# Admin Role
@pytest.fixture
def admin_role():
    return Role(id=str(uuid7()), name="admin")

# User Role
@pytest.fixture
def user_role():
    return Role(id=str(uuid7()), name="user")

# Test Admin
@pytest.fixture
def test_admin():
    admin = User(
        id=str(uuid7()),
        email="testadmin@gmail.com",
        password="hashedpassword",
        first_name="test",
        last_name="user",
        is_active=True
    )
    admin.role = admin_role
    return admin

# Test User
@pytest.fixture
def test_user():
    return User(
        id=str(uuid7()),
        email="testuser@gmail.com",
        password="hashedpassword",
        first_name="test",
        last_name="user",
        is_active=True
    )


@pytest.fixture()
def test_org():
    org = Organization(
        id=str(uuid7()),
        company_name="Organization 1"
    )
    return org

# admin role relation
@pytest.fixture
def admin_role_relation():
   return user_organization_roles(
        organization_id=test_org.id,
        user_id=test_admin.id,
        role_id=admin_role.id
    )

# user role relation
@pytest.fixture
def user_role_relation():
   return user_organization_roles(
        organization_id=test_org.id,
        user_id=test_user.id,
        role_id=user_role.id
    )

@pytest.fixture
def access_token_user(test_user):
    return user_service.create_access_token(user_id=test_user.id)


@pytest.fixture
def random_access_token():
    return user_service.create_access_token(user_id=str(uuid7()))


def test_remove_role_successful(
    mock_db_session,
    test_org,
    test_user,
    user_role,
    test_admin,
    admin_role,
    access_token_user
):
    mock_db_session.get.side_effect = [test_org, test_user, user_role]
    mock_db_session.execute().scalar_one_or_none.return_value = admin_role
    mock_role_service.get_user_role_relation = user_role_relation

    # Make request
    headers = {'Authorization': f'Bearer {access_token_user}'}
    put_url = f"/api/v1/organizations/{test_org.id}/users/{test_user.id}/roles/{user_role.id}"
    response = client.put(put_url, headers=headers)
    assert response.status_code == 200
    assert response.json()['message'] == "User successfully removed from role"


def test_remove_role_unsuccessful(
    mock_db_session,
    test_org,
    test_user,
    user_role,
    test_admin,
    admin_role,
    access_token_user
):
    headers = {'Authorization': f'Bearer {access_token_user}'}
    put_url = f"/api/v1/organizations/{test_org.id}/users/{test_user.id}/roles/{user_role.id}"

    # NON-ADMIN
    mock_db_session.execute().scalar_one_or_none.return_value = user_role
    mock_db_session.get.side_effect = [None, test_user, user_role]
    response = client.put(put_url, headers=headers)
    assert response.status_code == 401
    assert response.json()['message'] == "Insufficient permission. Admin required."

    # WRONG org_id
    mock_db_session.get.side_effect = [None, test_user, user_role]
    mock_db_session.execute().scalar_one_or_none.return_value = admin_role
    response = client.put(put_url, headers=headers)
    assert response.status_code == 404
    assert response.json()['message'] == "Organization does not exist"

    # WRONG user_id
    mock_db_session.get.side_effect = [test_org, None, user_role]
    mock_db_session.execute().scalar_one_or_none.return_value = admin_role
    response = client.put(put_url, headers=headers)
    assert response.status_code == 404
    assert response.json()['message'] == "User does not exist"

    # WRONG role_id
    mock_db_session.get.side_effect = [test_org, test_user, None]
    mock_db_session.execute().scalar_one_or_none.return_value = admin_role
    response = client.put(put_url, headers=headers)
    assert response.status_code == 404
    assert response.json()['message'] == "Role does not exist"

    # USER NOT IN ROLE
    mock_db_session.get.side_effect = [test_org, test_user, user_role]
    mock_db_session.execute().fetchone.return_value = None
    response = client.put(put_url, headers=headers)
    assert response.status_code == 403
    assert response.json()['message'] == "User not found in role"

    # INVALID ROLE NAME
    user_role.name = "ghost"
    mock_db_session.get.side_effect = [test_org, test_user, user_role]
    response = client.put(put_url, headers=headers)
    assert response.status_code == 400
    assert response.json()['message'] == "Invalid role"