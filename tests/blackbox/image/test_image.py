import sys
from threading import Thread

from httpx import HTTPError, get
from pytest import fixture
from yellowbox.containers import get_ports, killing
from yellowbox.image_build import build_image
from yellowbox.retry import RetrySpec


@fixture(scope="session")
def image(docker_client):
    with build_image(docker_client, 'heksher', path='.', remove_image=False) as image:
        yield image


def test_image_builds(image):
    pass


def test_startup_healthy(image, docker_client, monkeypatch, sql_service, purge_sql):
    env = {
        'HEKSHER_DB_CONNECTION_STRING': sql_service.host_connection_string(),
        'HEKSHER_STARTUP_CONTEXT_FEATURES': 'user;trust;theme',
    }

    with killing(docker_client.containers.create(image, environment=env, ports={80: 0})) as container:
        container.start()
        log_stream = container.logs(stream=True)

        def pipe():
            for line_b in log_stream:
                line = str(line_b, 'utf-8').strip()
                print(line, file=sys.stderr)

        pipe_thread = Thread(target=pipe)
        pipe_thread.start()

        container.reload()
        container_port = get_ports(container)[80]

        retry_spec = RetrySpec(0.5, 10)

        retry_spec.retry(lambda: get(f'http://localhost:{container_port}/api/health').raise_for_status(), HTTPError)

        response = get(f'http://localhost:{container_port}/api/health')
        response.raise_for_status()
        assert response.json()['version']
        response = get(f'http://localhost:{container_port}/docs')
        response.raise_for_status()
        response = get(f'http://localhost:{container_port}/redoc')
        response.raise_for_status()
        response = get(f'http://localhost:{container_port}/api/v1/context_features')
        response.raise_for_status()
    container.remove(v=True)


def test_startup_doc_only_healthy(image, docker_client, monkeypatch):
    env = {
        'DOC_ONLY': 'true'
    }

    with killing(docker_client.containers.create(image, environment=env, ports={80: 0})) as container:
        container.start()
        log_stream = container.logs(stream=True)

        def pipe():
            for line_b in log_stream:
                line = str(line_b, 'utf-8').strip()
                print(line, file=sys.stderr)

        pipe_thread = Thread(target=pipe)
        pipe_thread.start()

        container.reload()
        container_port = get_ports(container)[80]

        retry_spec = RetrySpec(0.5, 10)

        retry_spec.retry(lambda: get(f'http://localhost:{container_port}/api/health').raise_for_status(), HTTPError)

        response = get(f'http://localhost:{container_port}/api/health')
        response.raise_for_status()
        assert response.json()['version']
        response = get(f'http://localhost:{container_port}/docs')
        response.raise_for_status()
        response = get(f'http://localhost:{container_port}/redoc')
        response.raise_for_status()
        response = get(f'http://localhost:{container_port}/api/v1/context_features')
        assert response.is_error
    container.remove(v=True)
