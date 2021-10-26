from unittest.mock import MagicMock

from pytest import fixture, mark

from heksher.health_monitor import HealthMonitor, HealthStatus


@fixture
def monitor(mock_engine) -> HealthMonitor:
    monitor = HealthMonitor(extra={'glob_a': ['a', 1, 3]})
    monitor._engine = mock_engine
    return monitor


@mark.asyncio
async def test_happy_flow(monitor: HealthMonitor, mock_engine):
    version_mock = MagicMock()
    version_mock.scalar_one_or_none.return_value = '1.0.0'
    mock_engine.connection.execute.return_value = version_mock
    check = await monitor._check()
    assert check.status == HealthStatus.Healthy
    assert check.extra == {
        'glob_a': ['a', 1, 3],
        'db_version': '1.0.0'
    }


@mark.asyncio
async def test_empty_version(monitor: HealthMonitor, mock_engine):
    version_mock = MagicMock()
    version_mock.scalar_one_or_none.return_value = None
    mock_engine.connection.execute.return_value = version_mock
    monitor._engine = mock_engine
    check = await monitor._check()
    assert check.status == HealthStatus.Failed
    assert check.extra == {
        'glob_a': ['a', 1, 3],
        'db_version': None
    }


@mark.asyncio
async def test_failed_to_connect(monitor: HealthMonitor, mock_engine):
    version_mock = MagicMock()
    version_mock.scalar_one_or_none.side_effect = Exception
    mock_engine.connection.execute.return_value = version_mock
    check = await monitor._check()
    assert check.status == HealthStatus.Failed
