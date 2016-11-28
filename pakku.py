#coding=utf-8
from pytrade import *

import re
from xml.dom.minidom import parseString
import zlib

port=8887
THRESHOLD=15 # in seconds

danmaku_re=re.compile(r'https?://comment\.bilibili\.com/\d+\.xml')
taolus={
    '2333...': re.compile(r'^23{3,}$'),
    '6666...': re.compile(r'^6{4,}$'),
    'FFF...': re.compile(r'^[fF]+$'),
    'hhh...': re.compile(r'^[hH]+$'),
}

@fallback(Pass)
def on_req(req,py):
    if danmaku_re.match(req.url):
        py.log()
        req.headers.pop('If-Modified-Since',None)
        return Go

@fallback(Go)
def on_res(req,res,py):
    py.log()
    
    if res.code!=200:
        return

    xml=parseString(res.text)
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
    
    print('!! %d danmus filtered'%cn)
    return Response(
        status=200,
        headers={
            'Content-Type': 'text/xml;charset=utf-8',
            'Access-Control-Allow-Origin': '*',
        },
        body=xml.toxml(),
    )

proxy(port,request=on_req,response=on_res)