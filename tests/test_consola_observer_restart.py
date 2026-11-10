"""Regresion del arranque tras cerrar un observador con conexiones TCP pendientes."""
import errno
import importlib.util
from pathlib import Path
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('console_restart', ROOT / 'consolas_mininet_v1/consola_sdn.py')
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


class SocketWithPendingConnections:
    """Un puerto en espera exige REUSEADDR; un listener activo sigue siendo exclusivo."""
    def __init__(self, listening=False):
        self.options, self.address, self.closed = {}, None, False
        self.listening = listening

    def setsockopt(self, level, option, value):
        self.options[(level, option)] = value

    def bind(self, address):
        if self.listening or not self.options.get((socket.SOL_SOCKET, socket.SO_REUSEADDR)):
            raise OSError(errno.EADDRINUSE, 'Address already in use')
        self.address = address

    def getsockname(self):
        return self.address

    def listen(self, backlog):
        self.backlog = backlog

    def close(self):
        self.closed = True


class RestartTests(unittest.TestCase):
    def test_previous_probe_would_fail_but_real_server_reuses_pending_address(self):
        address = ('127.0.0.1', 8768)
        old_probe = SocketWithPendingConnections()
        with self.assertRaises(OSError):
            old_probe.bind(address)
        actual_socket = SocketWithPendingConnections()
        with patch('socket.socket', return_value=actual_socket), patch('socket.getfqdn', return_value='test'):
            server = console.bind_observer(address, console.BaseHTTPRequestHandler)
        self.assertEqual(actual_socket.address, address)
        self.assertTrue(actual_socket.options[(socket.SOL_SOCKET, socket.SO_REUSEADDR)])
        self.assertFalse(server.allow_reuse_port)
        console.close_observer(server, serving=False)
        self.assertTrue(actual_socket.closed)

    def test_active_listener_is_not_shared_or_stopped(self):
        actual_socket = SocketWithPendingConnections(listening=True)
        listener = 'LISTEN 0 5 192.168.56.107:8769 0.0.0.0:* users:(("python3",pid=123,fd=4))'
        with patch('socket.socket', return_value=actual_socket), patch.object(console.subprocess, 'run', return_value=SimpleNamespace(stdout=listener)) as query:
            with self.assertRaisesRegex(ValueError, '8769.*direccion en uso') as error:
                console.bind_observer(('192.168.56.107', 8769), console.BaseHTTPRequestHandler)
        self.assertIn('pid=123', str(error.exception))
        self.assertTrue(actual_socket.closed)
        self.assertEqual(query.call_args.args[0], ['ss', '-H', '-ltnp', 'sport = :8769'])

    def test_failure_before_serve_forever_does_not_deadlock_in_shutdown(self):
        server = Mock()
        console.close_observer(server, serving=False)
        server.shutdown.assert_not_called()
        server.server_close.assert_called_once()
        console.close_observer(None, serving=False)

    def test_running_server_is_shutdown_and_closed(self):
        server = Mock()
        console.close_observer(server, serving=True)
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
