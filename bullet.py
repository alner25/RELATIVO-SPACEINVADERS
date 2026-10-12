import random
import pygame

class Bullet:
    def __init__(self,x,y,bullet_type="rapid"):
        self.bullet_type=bullet_type
        if bullet_type=="strong": self.width,self.height,self.speed,self.damage=28,44,15,4
        else: self.width,self.height,self.speed,self.damage=18,34,17,1
        self.x,self.y=float(x),float(y); self.is_active=True; self.pulse=0
        try:
            image=pygame.image.load("assets/images/bullet.png").convert_alpha(); self.image=pygame.transform.scale(image,(self.width,self.height))
        except (pygame.error,FileNotFoundError):
            self.image=pygame.Surface((self.width,self.height),pygame.SRCALPHA); pygame.draw.rect(self.image,(240,240,255),self.image.get_rect(),border_radius=5)
    def update(self):
        if self.is_active: self.y-=self.speed; self.pulse+=.35; self.is_active=self.y>=-self.height
    def get_rect(self): return pygame.Rect(int(self.x),int(self.y),self.width,self.height)
    def draw(self,screen):
        if not self.is_active:return
        cx=int(self.x+self.width/2); bottom=int(self.y+self.height); glow=2+int(2*(1+__import__('math').sin(self.pulse)))
        pygame.draw.line(screen,(245,175,70) if self.bullet_type=="strong" else (100,200,255),(cx,bottom),(cx,int(self.y)-10),glow)
        screen.blit(self.image,(int(self.x),int(self.y)))

class BulletManager:
    def __init__(self):
        self.bullets=[]; self.normal_fire_delay=105; self.rapid_fire_delay=70; self.last_shot=0; self.rapid_fire=True; self.rapid_fire_end=0; self.strong_bullets=0
    def activate_rapid_fire(self,duration=999999999): self.rapid_fire=True; self.rapid_fire_end=pygame.time.get_ticks()+duration
    def update_powerups(self):
        if self.rapid_fire and self.rapid_fire_end and pygame.time.get_ticks()>=self.rapid_fire_end: self.rapid_fire=False
    def shoot(self,x,y):
        now=pygame.time.get_ticks(); self.update_powerups(); delay=self.rapid_fire_delay if self.rapid_fire else self.normal_fire_delay
        if now-self.last_shot<delay:return False
        typ="strong" if self.strong_bullets>0 else "rapid"
        if typ=="strong":self.strong_bullets-=1
        self.bullets.append(Bullet(x,y,typ)); self.last_shot=now; return True
    def update(self):
        self.update_powerups()
        for b in self.bullets:b.update()
        self.bullets=[b for b in self.bullets if b.is_active]
    def draw(self,screen):
        for b in self.bullets:b.draw(screen)
    def new_wave(self,wave):self.strong_bullets+=1
    def enemy_destroyed(self):
        if random.random()<.20:self.strong_bullets+=1; return True
        return False
    def clear(self):self.bullets.clear()
    def get_active_bullets(self):return list(self.bullets)
