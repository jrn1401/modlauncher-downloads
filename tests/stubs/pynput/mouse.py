class Button:
    left="Button.left"; right="Button.right"; middle="Button.middle"
class Controller:
    def __init__(self): self.position=(0,0); self.log=[]
    def click(self,b,n=1): self.log.append(("click",b,n,self.position))
    def move(self,dx,dy): self.log.append(("move",dx,dy))
    def scroll(self,dx,dy): self.log.append(("scroll",dy))
class Listener:
    def __init__(self,*a,**k): self.daemon=False
    def start(self): pass
    def stop(self): pass
