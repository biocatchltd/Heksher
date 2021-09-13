from docker import DockerClient
from pytest import fixture


@fixture(scope='session')
def docker_client():
    # todo improve when yellowbox is upgraded
    try:
        ret = DockerClient.from_env()
        ret.ping()
    except Exception:
        return DockerClient(base_url='tcp://localhost:2375')
    else:
        return ret
