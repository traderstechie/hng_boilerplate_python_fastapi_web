import pytest
from decouple import config
from uuid_extensions import uuid7
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app
from api.db.database import get_db
from api.v1.services.user import user_service
from api.v1.models import User, Organisation, BillingPlan
from api.v1.services.payment import payment_service, payment_gateway_service as pg_service


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
def mock_payment_service():
    with patch(
        "api.v1.services.payment.payment_service", autospec=True
    ) as payment_service_mock:
        yield payment_service_mock


@pytest.fixture
def mock_gateway_service():
    with patch(
        "api.v1.services.payment.payment_gateway_service", autospec=True
    ) as gateway_service_mock:
        yield gateway_service_mock


@pytest.fixture()
def test_org():
    org = Organisation(id=str(uuid7()), name="Org 1")
    return org


@pytest.fixture()
def test_bill_plan(test_org):
    bill_plan = BillingPlan(
        organisation_id=test_org.id,
        duration="Monthly",
        id=str(uuid7()),
        currency="NGN",
        description="",
        name="BP 1",
        price=5000
    )
    return bill_plan


# Test User
@pytest.fixture
def test_user():
    user = User(
        id=str(uuid7()),
        email="testuser@gmail.com",
        password="hashedpassword",
        first_name="test",
        last_name="user",
        is_active=True,
    )
    return user


@pytest.fixture
def access_token_user(test_user):
    return user_service.create_access_token(user_id=test_user.id)


@pytest.fixture
def random_access_token():
    return user_service.create_access_token(user_id=str(uuid7()))


def test_configure_payment_successful(
    mock_db_session,
    test_user,
    test_bill_plan,
    access_token_user,
):
    mock_db_session.query().filter().first.return_value = test_user
    mock_db_session.query().get.return_value = test_bill_plan

    # Make request
    headers = {"Authorization": f"Bearer {access_token_user}"}
    get_url = f"/api/v1/payments/configure/{test_bill_plan.id}/flutterwave"
    response = client.get(get_url, headers=headers)
    assert response.status_code == 200

    resp_d = response.json()
    assert resp_d['success'] == True
    assert resp_d["message"] == "Payment data configured successfully"

    data =  resp_d['data']
    assert data['user_email'] == test_user.email
    assert data['price'] == test_bill_plan.price
    assert data['tx_ref'].startswith(test_user.id)
    assert data['currency'] == test_bill_plan.currency
    assert data['payment_title'] == "Convey AI Video Suites"
    assert data['public_key'] == config('RAVE_PUBLIC_KEY_TEST')
    assert data['payment_description'] == "User subscription payment"
    assert data['action_url'] == pg_service.FLUTTERWAVE_ONE_OFF_PAY_URL
    assert data['user_name'] == f"{test_user.first_name} {test_user.last_name}"
    assert data['redirect_url'] == f"http://testserver/api/v1/payments/handle/{test_bill_plan.id}/flutterwave"
    


def test_configure_payment_unsuccessful(
    mock_db_session,
    test_user,
    test_bill_plan,
    access_token_user,
):
    headers = {"Authorization": f"Bearer {access_token_user}"}
    mock_db_session.query().filter().first.return_value = test_user
    mock_db_session.query().get.return_value = test_bill_plan

    # NON-FLUTTERWAVE
    get_url = f"/api/v1/payments/configure/{test_bill_plan.id}/anothergateway"
    response = client.get(get_url, headers=headers)
    assert response.status_code == 403
    assert response.json()["message"] == "Only fullterwave supported for now"
    # reset url to correct one
    get_url = f"/api/v1/payments/configure/{test_bill_plan.id}/flutterwave"


    # WRONG billing plan id
    mock_db_session.query().get.return_value = None
    response = client.get(get_url, headers=headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Billing plan not found."
    # reset billing plan mock to correct one
    mock_db_session.query().get.return_value = test_bill_plan


    # NO AUTH
    response = client.get(get_url)
    assert response.status_code == 401
    assert response.json()['message'] == 'Not authenticated'
