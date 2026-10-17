"""Bound DNS waits and share one lookup per configured dependency hostname."""
from concurrent.futures import ThreadPoolExecutor,TimeoutError
from ipaddress import ip_address
import socket
from threading import Lock
import time

_executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='dependency-dns')
_lock=Lock()
_entries={}


def resolve_host(host):
    try:ip_address(host);return host
    except ValueError:pass
    now=time.monotonic()
    with _lock:
        entry=_entries.setdefault(host,{'address':None,'until':0,'future':None})
        if entry['address'] and now<entry['until']:return entry['address']
        if entry['future'] is None:
            if now<entry['until']:
                if entry['address']:return entry['address']
                raise OSError('Dependency address unavailable')
            entry['future']=_executor.submit(socket.getaddrinfo,host,None,0,socket.SOCK_STREAM)
        future=entry['future'];previous=entry['address']
    try:
        rows=future.result(timeout=.25)
        address=next((row[4][0] for row in rows if row[0]==socket.AF_INET),rows[0][4][0])
    except TimeoutError:
        if previous:return previous
        raise OSError('Dependency address lookup timed out') from None
    except OSError:
        with _lock:
            if entry['future'] is future:entry.update(future=None,until=time.monotonic()+1)
        if previous:return previous
        raise OSError('Dependency address unavailable') from None
    with _lock:
        if entry['future'] is future:entry.update(address=address,until=time.monotonic()+1,future=None)
    return address
