#coding=utf-8

import tornado.httpserver
import tornado.ioloop
import tornado.iostream
import tornado.web
import tornado.httpclient
import tornado.httputil
import socket
import requests
import threading
from contextlib import closing

def fetch_request(url, callback, **kwargs):
    tornado.httpclient.AsyncHTTPClient().fetch(tornado.httpclient.HTTPRequest(url, **kwargs), callback, raise_error=False)

### PATCH BEGIN ###

import re
from xml.dom.minidom import parseString
import zlib

port=8887
count=0
THRESHOLD=7

danmaku_re=re.compile(r'https?://comment\.bilibili\.com/\d+\.xml')
taolus={
    '2333...': re.compile(r'^23{3,}$'),
    '6666...': re.compile(r'^6{4,}$'),
    'FFF...': re.compile(r'^[fF]+$'),
}

def request_callback(self):
    """
    :param self: self.request.[method, uri, headers, body] ; self.[set_status, set_header, write, finish]
    :return: True->放行并拦截响应 ; False->放行; None->终止请求
    """
    
    if danmaku_re.match(self.request.uri):
        global count
        self.count=count
        count+=1
        self.request.headers.pop('If-Modified-Since',None)
        print(' -> #%4d %s (%dB) %s'%(self.count,self.request.method,len(self.request.body),self.request.uri))
        return True
    else:
        return False

def response_callback(self,resp):
    """
    :param self: self.request.[method, uri, headers, body] ; self.[set_status, set_header, write, finish]
    :param resp: resp.[code, reason, headers.get_all(), body]
    :return: True->正常返回 ; False->终止请求
    """
    print('<-  #%4d %s %s (%dB) %s'%(self.count,resp.code,resp.reason,len(resp.body),self.request.uri))
    
    if resp.code!=200:
        return True
    
    dat=zlib.decompress(resp.body,-zlib.MAX_WBITS).decode('utf-8','ignore')
    xml=parseString(dat)
    danmus=sorted([
        (elem.attributes['p'].value.split(','),elem.childNodes[0].data,elem)
        for elem in xml.getElementsByTagName('d') if elem.childNodes
    ], key=lambda item:float(item[0][0]))
    print('!! fetched %d danmus'%len(danmus))
    
    hist={} #text : (time, count, elem)

    def taolu(text):
        for k,v in taolus.items():
            if v.match(text):
                return k
        return text

    def get(time,text,elem):
        text=taolu(text)
        if text in hist and time-hist[text][0]>THRESHOLD:
            del hist[text]        
        if text not in hist:
            elem._original_text=text
            hist[text]=[time,1,elem]
            return False
        else:
            hist[text][1]+=1
            hist[text][2].childNodes[0].data=hist[text][2]._original_text+' [x%d]'%hist[text][1]
            return True
    
    cn=0
    for attrs,text,elem in danmus:
        time=float(attrs[0])
        if get(time,text,elem):
            elem.parentNode.removeChild(elem)
            cn+=1
    
    self.add_header('content-type','text/xml;charset=utf-8')
    print('!! %d danmus filtered'%cn)
    self.finish(xml.toxml())
    return False

### PATCH END ###

s=requests.Session()
s.trust_env=False #disable original proxy
thread_adapter=requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
s.mount('http://',thread_adapter)

def _async(f):
    def _real(*__,**_):
        threading.Thread(target=f,args=__,kwargs=_).start()
    return _real

@_async
def tornado_fetcher(ioloop, puthead, putdata, finish, method, url, headers, body):
    try:
        with closing(s.request(
                method, url, headers=headers, data=body, 
                stream=True, allow_redirects=False, timeout=30,
            )) as res:
            ioloop.add_callback(puthead,res.status_code,res.reason,res.headers.items())
            for content in res.raw.stream(128*1024, decode_content=False):
                ioloop.add_callback(putdata,content)
            ioloop.add_callback(finish)
    except Exception as e:
        ioloop.add_callback(puthead,500,'Internal Server Error',[('Content-Type','text/html')])
        ioloop.add_callback(putdata,'Internal server error:\n' + str(e))
        ioloop.add_callback(finish)

class ProxyHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ['GET', 'POST', 'HEAD', 'DELETE', 'PATCH', 'PUT', 'CONNECT']

    def compute_etag(self):
        return None # disable tornado Etag

    @tornado.web.asynchronous
    def get(self):
        def callback_puthead(code,reason,headers):
            self.set_status(code, reason)
            self._headers = tornado.httputil.HTTPHeaders()
            for k,v in headers:
                if k.lower() not in ['connection','transfer-encoding']:
                    self.add_header(k, v)
            self.flush()
        
        def callback_putdata(data):
            self.write(data)
            self.flush()
    
        def callback_finish():
            self.finish()        

        def handle_response(response):
            if response.error and not isinstance(response.error, tornado.httpclient.HTTPError):
                self.set_status(500)
                self.write('Internal server error:\n' + str(response.error))
            else:
                if _should_break and not response_callback(self,response):
                    return
                self.set_status(response.code, response.reason)
                self._headers = tornado.httputil.HTTPHeaders() # clear tornado default header

                for header, v in response.headers.get_all():
                    if header not in ('Content-Length', 'Transfer-Encoding', 'Connection'):
                        self.add_header(header, v) # some header appear multiple times, eg 'Set-Cookie'

                if response.body:
                    self.set_header('Content-Length', len(response.body))
                    self.write(response.body)
            self.finish()

        body = self.request.body or None
        try:
            if 'Proxy-Connection' in self.request.headers:
                del self.request.headers['Proxy-Connection']

            cmd=request_callback(self)
            if cmd is None:
                return
            else:
                _should_break=bool(cmd)

            if _should_break:
                fetch_request(
                    self.request.uri, handle_response,
                    method=self.request.method, body=body,
                    headers=self.request.headers, follow_redirects=False,
                    allow_nonstandard_methods=True
                )
            else:
                tornado_fetcher(
                    ioloop,
                    callback_puthead, callback_putdata, callback_finish,
                    self.request.method, self.request.uri, self.request.headers, body,
                )
        except tornado.httpclient.HTTPError as e:
            if hasattr(e, 'response') and e.response:
                handle_response(e.response)
            else:
                self.set_status(500)
                self.write('Internal server error:\n' + str(e))
                self.finish()

    post=get
    head=get
    delete=get
    patch=get
    put=get

    @tornado.web.asynchronous
    def connect(self):
        host, port = self.request.uri.split(':')
        client = self.request.connection.stream

        def client_close(data=None):
            if upstream.closed():
                return
            if data:
                upstream.write(data)
            upstream.close()

        def upstream_close(data=None):
            if client.closed():
                return
            if data:
                client.write(data)
            client.close()

        def start_tunnel():
            client.read_until_close(client_close, upstream.write)
            upstream.read_until_close(upstream_close, client.write)
            client.write(b'HTTP/1.0 200 Connection established\r\n\r\n')

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        upstream = tornado.iostream.IOStream(s)
        upstream.connect((host, int(port)), start_tunnel)


def run_proxy(port, start_ioloop=True):
    tornado.web.Application([
        (r'.*', ProxyHandler),
    ]).listen(port)
    if start_ioloop:
        global ioloop
        ioloop=tornado.ioloop.IOLoop.instance()
        ioloop.start()

if __name__ == '__main__':
    print ("Starting HTTP proxy on port %d" % port)
    run_proxy(port)
