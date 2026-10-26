class Key:
    pass
for n in ["space","enter","tab","backspace","esc","up","down","left","right","shift","ctrl","alt","home","end","page_up","page_down","delete","insert","f6","f7","f8"]+[f"f{i}" for i in range(1,13)]:
    setattr(Key, n, n)
class _KeyMeta(type):
    def __getitem__(cls, k):
        return getattr(cls, k)
Key = _KeyMeta("Key", (), {n: n for n in dir(Key) if not n.startswith("_")})
class KeyCode:
    @staticmethod
    def from_char(c): return c
class Controller:
    def __init__(self): self.log=[]
    def tap(self,k): self.log.append(("tap",k))
    def press(self,k): self.log.append(("press",k))
    def release(self,k): self.log.append(("release",k))
    def type(self,t): self.log.append(("type",t))
class HotKey:
    @staticmethod
    def parse(hk):
        if not hk or "<" not in hk and len(hk)>1 and "+" not in hk: raise ValueError("bad")
        return hk
class GlobalHotKeys:
    def __init__(self,m): self.m=m; self.daemon=False
    def start(self): pass
    def stop(self): pass
class Listener:
    def __init__(self,*a,**k): self.daemon=False
    def start(self): pass
    def stop(self): pass
