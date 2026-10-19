import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_environment_settings(monkeypatch):
    monkeypatch.setenv('APP_NAME', 'Isolated API')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://test:secret@localhost/test')
    settings = Settings(_env_file=None)
    assert settings.app_name == 'Isolated API'
    assert settings.app_env == 'test'
    assert settings.database_url.get_secret_value().startswith('postgresql+psycopg://')
    assert 'secret' not in repr(settings)


def test_database_required(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize('url', ['sqlite:///test.db', 'invalid', 'postgresql://localhost'])
def test_invalid_url(url):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=url)
    assert url not in str(error.value)


def test_invalid_environment():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url='postgresql://localhost/test', app_env='unknown')


def test_env_path_independent_of_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert Settings().database_url.get_secret_value()
