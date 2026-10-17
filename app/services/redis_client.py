"""Bound foreground Redis calls; Celery delivery retains its own retry policy."""
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from redis.connection import Connection,SSLConnection
from app.services.dependency_dns import resolve_host


def resolved_tcp(connection):
    hostname=connection.host
    connection.host=resolve_host(hostname)
    try:return Connection._connect(connection)
    finally:connection.host=hostname


class BoundedConnection(Connection):
    def _connect(self):return resolved_tcp(self)


class BoundedSSLConnection(SSLConnection):
    def _connect(self):
        sock=resolved_tcp(self)
        try:return self._wrap_socket_with_ssl(sock)
        except Exception:
            sock.close()
            raise


def foreground_redis(url):
    client=Redis.from_url(url,socket_connect_timeout=1,socket_timeout=1,retry=Retry(NoBackoff(),0))
    pool=client.connection_pool
    if pool.connection_class is Connection:pool.connection_class=BoundedConnection
    elif pool.connection_class is SSLConnection:pool.connection_class=BoundedSSLConnection
    return client
