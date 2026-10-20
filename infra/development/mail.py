#!/usr/bin/env python3
"""Private local development mail. Never use this receiver for hosted environments."""
import argparse
import email.policy
from email.parser import BytesParser
import os
from pathlib import Path
import socketserver
import ssl
import stat
import subprocess
import sys
import uuid


def private_directory(path):
    path = Path(path).absolute()
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Mail directory must be an owned, non-symlink directory with mode 0700')
    return path


def initialize(path):
    path = Path(path).absolute()
    path.mkdir(mode=0o700)  # Refuse existing paths; never replace keys or mail.
    private_directory(path)
    commands = [
        ['req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '30', '-keyout', 'ca.key', '-out', 'ca.pem', '-subj', '/CN=EvidenceAI Local Mail CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign'],
        ['req', '-new', '-newkey', 'rsa:3072', '-nodes', '-keyout', 'server.key', '-out', 'server.csr', '-subj', '/CN=localhost'],
        ['x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial', '-days', '7', '-out', 'server.pem', '-extfile', 'extensions.cnf'],
    ]
    (path / 'extensions.cnf').write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    for args in commands:
        subprocess.run(['openssl', *args], cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for item in path.iterdir():
        item.chmod(0o600)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        def reply(text):
            self.wfile.write((text + '\r\n').encode())
            self.wfile.flush()
        reply('220 localhost ESMTP')
        while line := self.rfile.readline(8192):
            command = line.split(b' ', 1)[0].strip().upper()
            if command in (b'EHLO', b'HELO', b'MAIL', b'RCPT', b'RSET', b'NOOP'):
                reply('250 OK')
            elif command == b'DATA':
                reply('354 End with dot')
                content = bytearray()
                while True:
                    piece = self.rfile.readline(8192)
                    if not piece:
                        return
                    if piece == b'.\r\n':
                        break
                    content.extend(piece[1:] if piece.startswith(b'..') else piece)
                    if len(content) > 65536:
                        reply('552 Message too large')
                        return
                if len(list(self.server.mail_directory.glob('*.eml'))) >= 100:
                    reply('452 Local mailbox full')
                    continue
                target = self.server.mail_directory / (uuid.uuid4().hex + '.eml')
                with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                    stream.write(content)
                reply('250 Accepted')
            elif command == b'QUIT':
                reply('221 Bye')
                return
            else:
                reply('502 Unsupported')


class Server(socketserver.TCPServer):
    # Single bounded connection at a time; no public or configurable bind address.
    allow_reuse_address = True
    def __init__(self, directory, port=1465):
        self.mail_directory = private_directory(directory)
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(directory / 'server.pem', directory / 'server.key')
        super().__init__(('127.0.0.1', port), Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        try:
            return self.context.wrap_socket(connection, server_side=True), address
        except Exception:
            connection.close()
            raise

    def handle_error(self, request, client_address):
        # Never emit protocol content, email addresses or tokens in logs.
        pass


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'serve', 'view', 'api'])
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'init':
        initialize(args.directory)
        print('Local CA and server certificate created. No system trust changes.')
        return
    directory = private_directory(args.directory)
    if args.command == 'serve':
        with Server(directory) as server:
            print('TLS SMTP listening on 127.0.0.1:1465. Stop with Control-C.', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    elif args.command == 'view':
        if not sys.stdout.isatty():
            raise ValueError('View requires a private interactive terminal; redirection is refused')
        files = sorted(directory.glob('*.eml'), key=lambda p: p.stat().st_mtime_ns)
        if not files:
            print('No mail received.')
            return
        path = files[-1]
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('Unsafe mailbox file')
        message = BytesParser(policy=email.policy.default).parsebytes(path.read_bytes())
        # Strip terminal control sequences from untrusted mail text.
        body = str(message['To']) + '\n' + message.get_content()
        print(''.join(c for c in body if c in '\n\t' or (c.isprintable() and c != '\x1b')))
    else:
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / 'apps/api'))
        from app.core.config import Settings
        if Settings().app_env != 'development':
            raise ValueError('Development mail launcher refuses non-development settings')
        os.environ.update(APP_ENV='development', AUTH_ALLOW_INSECURE_HTTP='true',
            TRUSTED_FRONTEND_ORIGINS='["http://localhost:3000"]',
            REGISTRATION_PUBLIC_ORIGIN='http://localhost:3000', REGISTRATION_EMAIL_ENABLED='true',
            SMTP_HOST='127.0.0.1', SMTP_PORT='1465', SMTP_SENDER='noreply@evidenceai.test',
            SMTP_CA_FILE=str(directory / 'ca.pem'), SMTP_USERNAME='', SMTP_PASSWORD='')
        # Validate all overrides before starting; database URL still comes from existing .env.
        Settings()
        os.chdir(root / 'apps/api')
        os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-proxy-headers', '--no-access-log'])


if __name__ == '__main__':
    main()
