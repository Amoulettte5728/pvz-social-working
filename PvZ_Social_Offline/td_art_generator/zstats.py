import re,sys
# id: (hp, weight, value, firstAllowWave, propIdList)   -- original PvZ values
S={2:(270,4000,1,1,0),3:(270,4000,1,1,0),4:(270,0,1,1,4),5:(270,4000,2,1,1),7:(270,2000,3,10,0),
   8:(500,2000,2,5,0),9:(500,1500,3,10,0),10:(270,1000,2,1,3),11:(270,3000,4,1,2),13:(270,3500,4,1,5),
   14:(270,2000,7,1,6),15:(500,1000,3,10,12),16:(3000,1500,10,15,0),18:(270,1000,8,1,7),19:(270,0,2,1,0),
   20:(270,4000,1,1,0),26:(270,2000,2,1,0),34:(270,1000,8,1,7),36:(6000,1000,15,20,0),101:(270,0,1,1,0)}
p=sys.argv[1]; s=open(p,encoding='utf-8',newline='').read(); n=0
def rep(m):
    global n
    tagtxt=m.group(0); zid=int(re.search(r'zombieId="(\d+)"',tagtxt).group(1))
    if zid not in S or ' hp="' in tagtxt: return tagtxt
    hp,w,v,fw,pr=S[zid]; n+=1
    return tagtxt[:-1]+f' hp="{hp}" weight="{w}" value="{v}" firstAllowWave="{fw}" propIdList="{pr}" hpCoefficient="0.1">'
s=re.sub(r'<Zombie [^>]*>',rep,s)
open(p,'w',encoding='utf-8',newline='').write(s); print('updated',n)
