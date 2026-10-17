from concurrent.futures import ThreadPoolExecutor
from threading import Event
import socket,time
from uuid import uuid4
import pytest
from app.services.dependency_dns import resolve_host


def test_slow_dns_lookup_has_bounded_wait_and_is_shared(monkeypatch):
    release=Event();calls=[];host='slow-'+uuid4().hex
    def slow(*args):
        calls.append(args[0]);release.wait(2)
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',0))]
    monkeypatch.setattr(socket,'getaddrinfo',slow)
    def attempt(_):
        start=time.monotonic()
        with pytest.raises(OSError,match='timed out'):resolve_host(host)
        return time.monotonic()-start
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:durations=list(pool.map(attempt,range(3)))
        assert max(durations)<1 and calls==[host]
    finally:release.set()


def test_ip_literal_needs_no_dns(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args:pytest.fail('IP literal must not resolve'))
    assert resolve_host('127.0.0.1')=='127.0.0.1'


def test_redis_tls_preserves_original_certificate_hostname(monkeypatch):
    from redis.connection import Connection
    from app.services.redis_client import BoundedSSLConnection
    monkeypatch.setattr('app.services.redis_client.resolve_host',lambda _: '127.0.0.1')
    calls=[];sock=object()
    def tcp(connection):calls.append(('tcp',connection.host));return sock
    def tls(connection,actual):calls.append(('tls',connection.host));assert actual is sock;return sock
    monkeypatch.setattr(Connection,'_connect',tcp)
    monkeypatch.setattr(BoundedSSLConnection,'_wrap_socket_with_ssl',tls)
    connection=BoundedSSLConnection(host='redis.example',ssl_check_hostname=True)
    assert connection._connect() is sock
    assert calls==[('tcp','127.0.0.1'),('tls','redis.example')]
    assert connection.host=='redis.example' and connection.check_hostname
