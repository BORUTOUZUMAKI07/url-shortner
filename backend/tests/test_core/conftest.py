import pytest


@pytest.fixture(autouse=True)
def cleanup():
    pass


@pytest.fixture
def db():
    return None


@pytest.fixture
def test_user():
    return None


@pytest.fixture
def test_workspace():
    return None


@pytest.fixture
def test_url():
    return None


@pytest.fixture(autouse=True)
def mock_external_services():
    pass
