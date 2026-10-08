import sys,zlib,struct,glob,os
def tags(path):
    d=open(path,'rb').read()
    sig=d[:3]
    if sig==b'CWS': body=zlib.decompress(d[8:])
    elif sig==b'FWS': body=d[8:]
    elif sig==b'ZWS':
        import lzma
        body=lzma.LZMADecompressor(lzma.FORMAT_RAW,filters=[{'id':lzma.FILTER_LZMA1,'dict_size':1<<24,**{}}]).decompress(d[17:]) if False else None
        raise Exception('lzma')
    else: raise Exception('not swf')
    nb=body[0]>>3; rl=(5+4*nb+7)//8; p=rl+4
    out=[]
    while p<len(body):
        h=struct.unpack_from('<H',body,p);p+=2
        code=h[0]>>6; ln=h[0]&63
        if ln==63: ln=struct.unpack_from('<I',body,p)[0];p+=4
        out.append((code,body[p:p+ln]));p+=ln
        if code==0: break
    return d[3],out
def syms(path):
    v,t=tags(path); names=[]
    for c,b in t:
        if c==76:
            n=struct.unpack_from('<H',b)[0];q=2
            for i in range(n):
                cid=struct.unpack_from('<H',b,q)[0];q+=2
                e=b.index(b'\0',q);names.append((cid,b[q:e].decode('utf-8','replace')));q=e+1
    return names
if __name__=='__main__':
    for f in sys.argv[1:]:
        try:
            for cid,n in syms(f): print(os.path.basename(f),cid,n)
        except Exception as e: print(os.path.basename(f),'ERR',e)
