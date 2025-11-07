import machine
import ssd1306
from misakifont import MisakiFont
#https://github.com/Tamakichi/pico_MicroPython_misakifont/tree/main
import time
#参考情報
#https://wisteriahill.sakura.ne.jp/CMS/WordPress/2023/04/30/pi-pico-setup-micropython-memo-2/

#クラス化
    
class Ssd1306_i2c_JAFont:
    #初期化
    #x:画面の横サイズ、y:画面の縦サイズ、i2c_id：i2cアドレス、i2c:machine.I2Cの値を渡す
    def __init__(self,i2c,i2c_id=0x3c,x=128,y=64):
        self.oled=ssd1306.SSD1306_I2C(x, y, i2c)
        self.XMAX=x
        self.YMAX=y
        self.mf=MisakiFont()
        self.fcolor=1
        self.fsize=1
        
    #フォントサイズの初期設定
    def setDefaultFsize(self,fsize):
        self.fsize=self.fsize_chk(fsize)
     
    #表示の消去
    def clearDisp(self):
        self.oled.fill(0)
        self.show()
        
    #画面の表示処理
    def show(self):
        #time.sleep(0.1)
        self.oled.show()
        
    #表示できる文字列長の取得
    def str_len_MAX(self,fsize):
        wakuX=int(self.XMAX / (fsize*8))
        wakuY=int(self.YMAX / (fsize*8))
        lenMax=wakuX*wakuY
        return lenMax
    
    #フォントサイズのチェック
    def fsize_chk(self,fsize):
        fsize_r=fsize
        if fsize_r<1 :fsize_r=1
        elif fsize_r*8 > self.YMAX : fsize_r=self.YMAX/fsize_r
        elif fsize_r*8 > self.XMAX : fsize_r=self.XMAX/fsize_r
        return fsize_r
    
    #文字列長のチェック、長すぎたら切り出す    
    def check_str_len(self,str_='',fsize=1):
        fsize=self.fsize_chk(fsize)
        lenMax=self.str_len_MAX(fsize)
        return str_[:lenMax]
    
    #文字を表示する処理  （内部用）
    def show_bitmap(self, fd, x, y, size,disp=True ):
        for row in range(0, 7):
            for col in range(0, 7):
                if (0x80 >> col) & fd[row]:
                    self.oled.fill_rect(int(x + col * size), int(y + row * size), size, size, self.fcolor)
        if disp:self.show()
        
    #文字列を表示する処理。基本これだけを使う。
    #str_:表示したい文字列
    #x:画面の横位置、y:画面の縦位置、fsize:フォントサイズ、
    #dispImmidiate：この文字列をすぐに表示、clearDisp：文字列表示前に画面クリア
    def dispStr(self,str_,x=0,y=0,fsize=-1,dispImmidiate=True,clearDisp=True):
        if fsize==-1 : fsize=self.fsize
    
        fsize=self.fsize_chk(fsize)
        str_c=self.check_str_len(str_,fsize=fsize)
        print(str_c)
        if clearDisp:self.oled.fill(0)

        for c in str_c:
            d=self.mf.font(ord(c))
            self.show_bitmap(d, x, y,  fsize,disp=False )
            x += 8 * fsize
            if x >= 128:
                x = 0
                y += 8 * fsize
            if y >= 32:
                y = 0
        if dispImmidiate:self.show()
        
#テスト用
if __name__ == "__main__":
    sda = machine.Pin(0)
    scl = machine.Pin(1)
    i2c = machine.I2C(0, sda=sda, scl=scl, freq=1_000_000)
    
    oled=ssd1306_i2c_JAFont(i2c,i2c_id=0x3c,x=128,y=32)
    oled.dispStr('これはテストです。',dispImmidiate=True  )
    time.sleep(1)
    oled.dispStr('これはテストですよ',x=0,y=16,dispImmidiate=True  )
    time.sleep(1)
    oled.dispStr('Add 16 笑顔。',fsize=2, dispImmidiate=True  )                  
    time.sleep(1)
    
    oled.setDefaultFsize(3)
    
    oled.dispStr('これはテストです。',dispImmidiate=True  )
    time.sleep(1)
    oled.dispStr('これはテストですよ',x=0,y=16,dispImmidiate=True ,clearDisp=False )
    time.sleep(1)
    oled.dispStr('Add 16 笑顔。',fsize=4,dispImmidiate=True  )                  
    time.sleep(1)        