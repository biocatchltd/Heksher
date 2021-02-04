import json
import sys


def _iter_build_log(build_log):
    """Iterate over lines of the build log"""
    remaining = b""
    for chunk in build_log:
        if b'\n' not in chunk:
            remaining += chunk
            continue
        if remaining:
            chunk = remaining + chunk
            remaining = b""

        str_chunk = chunk.decode("utf-8")
        lines = str_chunk.splitlines()

        if not str_chunk.endswith('\n'):
            remaining += lines.pop().encode("utf-8")

        for line in lines:
            obj = json.loads(line)
            stream = obj.get("stream")
            if stream:
                yield stream.strip()


def test_image_builds(docker_client):
    build_log = docker_client.api.build(path=".", tag='heksher:testing', rm=True)

    # Wait till build is finished.
    for line in _iter_build_log(build_log):
        print(line)

    assert docker_client.images.get('heksher:testing')
    docker_client.images.remove('heksher:testing', force=True, noprune=True)
