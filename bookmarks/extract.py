"""Bounded public HTTP extraction in a credential-free, killable subprocess.

Resolve/validate every hop, connect to the checked IP, retain hostname TLS/SNI.
No environment proxies, cookies, compression, private networks or custom ports.
"""
import asyncio
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import sys
from urllib.parse import urljoin, urlsplit

MAX_BYTES=1024*1024


def public_addresses(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username is not None or p.password is not None:
        raise ValueError('Only public HTTP(S) URLs are supported')
    if any(ord(c)<33 or ord(c)==127 for c in url): raise ValueError('Unsafe URL')
    port=p.port or (443 if p.scheme=='https' else 80)
    if port not in (80,443): raise ValueError('Port not allowed')
    addresses=list(dict.fromkeys(a[4][0] for a in socket.getaddrinfo(p.hostname,port,type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('Nonpublic destination')
    return p,port,addresses


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skipping=0; self.size=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'): self.skipping+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript') and self.skipping: self.skipping-=1
        if tag in ('p','div','h1','h2','li','br') and not self.skipping: self.parts.append('\n')
    def handle_data(self,data):
        if not self.skipping and self.size<30000:
            value=data[:30000-self.size]; self.parts.append(value); self.size+=len(value)


def text_from_html(html):
    parser=ArticleText(); parser.feed(html)
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())[:30000]


def fetch_public(url):
    for _ in range(4):
        parsed,port,addresses=public_addresses(url)
        conn=http.client.HTTPConnection(parsed.hostname,port,timeout=5)
        try:
            sock=socket.create_connection((addresses[0],port),timeout=5)
            try:
                if parsed.scheme=='https': sock=ssl.create_default_context().wrap_socket(sock,server_hostname=parsed.hostname)
            except BaseException:
                sock.close(); raise
            conn.sock=sock
            path=parsed.path or '/'
            if parsed.query: path+='?'+parsed.query
            conn.request('GET',path,headers={'Host':parsed.netloc,'Accept-Encoding':'identity','User-Agent':'HermesBookmarks/0.1'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location: raise ValueError('Missing redirect')
                url=urljoin(url,location); continue
            if response.status!=200: raise ValueError('Page unavailable')
            if response.getheader('Content-Encoding','identity').lower() not in ('identity',''): raise ValueError('Encoded response unsupported')
            mime=response.getheader('Content-Type','').split(';')[0].strip().lower()
            if mime not in ('text/html','text/plain','application/xhtml+xml'): raise ValueError('Not a supported text page')
            body=response.read(MAX_BYTES+1)
            if len(body)>MAX_BYTES: raise ValueError('Page too large')
            text=body.decode('utf-8',errors='replace')
            result=text_from_html(text) if mime!='text/plain' else text[:30000]
            if not result.strip(): raise ValueError('Empty page')
            return result
        finally: conn.close()
    raise ValueError('Too many redirects')


async def extract_text(url):
    # A child process bounds DNS and slow-response time without leaving a
    # cancelled resolver thread alive in the plugin host.
    env={k:os.environ[k] for k in ('PATH','LANG','TMPDIR') if k in os.environ}
    child=await asyncio.create_subprocess_exec(sys.executable,str(Path(__file__).resolve()),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=env)
    try:
        output,_=await asyncio.wait_for(child.communicate(json.dumps({'url':url}).encode()),timeout=25)
        if child.returncode: raise ValueError('Article extraction failed')
        return json.loads(output)['text']
    finally:
        if child.returncode is None:
            child.kill(); await child.wait()


if __name__=='__main__':
    try: print(json.dumps({'text':fetch_public(json.load(sys.stdin)['url'])}))
    except Exception: sys.exit(1)
