"""TLS-only synthetic SMTP sink for the isolated staging fixture, never production."""
from email import policy
from email.parser import BytesParser
import hashlib,json,re,socketserver,ssl
from pathlib import Path

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        def reply(text):self.wfile.write((text+'\r\n').encode());self.wfile.flush()
        reply('220 fixture ESMTP')
        while line:=self.rfile.readline(10000):
            command=line.split(b' ',1)[0].strip().upper()
            if command in (b'EHLO',b'HELO'):reply('250 fixture')
            elif command in (b'MAIL',b'RCPT',b'RSET',b'NOOP'):reply('250 OK')
            elif command==b'DATA':
                reply('354 End with dot');parts=[]
                while (piece:=self.rfile.readline(10000)) not in (b'.\r\n',b''):
                    parts.append(piece)
                    if sum(map(len,parts))>65536:return
                message=BytesParser(policy=policy.default).parsebytes(b''.join(parts))
                token=re.search(r'#token=([A-Za-z0-9_-]{43})',message.get_content()).group(1)
                target=Path('/mail')/(hashlib.sha256(str(message['To']).encode()).hexdigest()+'.json')
                target.write_text(json.dumps({'token':token}));target.chmod(0o600)
                reply('250 Accepted synthetic fixture')
            elif command==b'QUIT':reply('221 Bye');return
            else:reply('502 Unsupported fixture command')

context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain('/mail/cert.pem','/mail/key.pem')
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    def get_request(self):
        socket,address=super().get_request();return context.wrap_socket(socket,server_side=True),address
with Server(('0.0.0.0',1465),Handler) as server:server.serve_forever()
