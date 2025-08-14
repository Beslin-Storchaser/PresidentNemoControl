# This example finds and connects to a peripheral running the
# UART service (e.g. ble_simple_peripheral.py).

# This example demonstrates the low-level bluetooth module. For most
# applications, we recommend using the higher-level aioble library which takes
# care of all IRQ handling and connection management. See
# https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble

#OLED MODE

import bluetooth
import random
import struct
import time
import micropython
from machine import Pin,PWM,SPI,Signal,I2C
#import max7219_8digit
from .ssd1306_i2c_JAFont import Ssd1306_i2c_JAFont
from debounced_input import DebouncedInput


from ble_advertising import decode_services, decode_name

from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)

_ADV_IND = const(0x00)
_ADV_DIRECT_IND = const(0x01)
_ADV_SCAN_IND = const(0x02)
_ADV_NONCONN_IND = const(0x03)

_UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_RX_CHAR_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX_CHAR_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

#基本はButtonと情報(Pin番号他)を共通化。
g_BUTTON_gpio=(0,2,4)       #Button 
g_BUTTON_gpio_Cen=(7,6,5)       #Button 
g_LEDPWM_gpio=(10,11,12)    #LED-btn,Central側はリレー出力
g_LEDHB_gpio=(15,)           #LED-HeartBeat for BLE
g_WIRED_gpio=(4,)          #有線無線判定。プルアップ。GNDなら有線。

g_BUTTONData=[False,0,True,0]   #for debounce_input callback
g_BUTTON=[]
g_LEDPWM=[]
g_LEDHB=0
g_LEDHBData=[]
g_WIRED=0
'''
#MAX7219個別設定-SPI,SS
g_MAX7219_gpio={
    "SCK":2,    #SCK-CLK
    "MOSI":3,    #MOSI-DIN
    "MISO":0,   #MISO-(Not Use)
    "CS":1      #SS-CS
}
g_MAX7219=0
g_MAX7219_DispData=" "*8
'''
#MAX7219個別設定-SPI,SS
g_OLED_gpio={
    "SCL":1,    #SCK-CLK
    "SDA":0,    #MOSI-DIN

}
g_OLED=0
g_OLED_DispData=" "*8

#_BUTTON_TYPE=('A','D','R') #ボタンタイプ
_BUTTON_TYPE=('Add','Down','Res') #ボタンタイプ

_BUTTON_TYPE_VAL=(1,-1,0)
_FACE_LIST=(
    '    ', #0=なし
    'あんない', #1
    'QRコード_クロ', #2
    'QRコード_シロ', #3
    'QRコードダブル', #4
    'エネルギー光線', #5
    'だいスマイル', #6
    'スマイル_あか', #7
    'スマイル＿きいろ', #8
    'とんらん', #9
    'ぼうえい', #10
    'いかり1', #11
    'いかり2', #12
    'じかん', #13
    'ぴえん', #14
    '7へんげ', #15
    'NOOISSY!' #16
    )
g_FACE_NUMBER=1
#initialize variables
MAX_VAL_ABS=999 
g_max_val=16 #初期値。今後ファイル読み出し対応予定
MIN_VAL_ABS=1
g_min_val=MIN_VAL_ABS
DURATION_LONG_PRESS=2500

g_onFirstTime=True

##ボタン押し下げ時のコールバック関数
def btn_callback(pin, pressed, duration_ms):
    global g_BUTTONData
    if (pressed):
        print("Pin-", pin, " Pressed:", duration_ms, "ms since last press")
        g_BUTTONData=[True,pin,True,duration_ms]
    if (pressed==False):
        print("Pin-", pin, " released:", duration_ms, "ms long press ")
        g_BUTTONData=[True,pin,False,duration_ms]

def valueAddSub1(cur:int,direc:int,val_min=g_min_val,val_max=g_max_val)->int:
    if direc!=1 and direc!=-1 and direc!=0:
        sys.abort()
        
    tmp_val=cur+direc
    if direc==0:tmp_val=val_min
    if tmp_val<val_min :
        tmp_val=val_max
    if tmp_val>val_max :
        tmp_val=val_min
    return tmp_val

class BLESimpleCentral:
    def __init__(self, ble):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)

        self._reset()

    def _reset(self):
        # Cached name and address from a successful scan.
        self._name = None
        self._addr_type = None
        self._addr = None

        # Callbacks for completion of various operations.
        # These reset back to None after being invoked.
        self._scan_callback = None
        self._conn_callback = None
        self._read_callback = None

        # Persistent callback for when new data is notified from the device.
        self._notify_callback = None

        # Connected device.
        self._conn_handle = None
        self._start_handle = None
        self._end_handle = None
        self._tx_handle = None
        self._rx_handle = None

    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            if adv_type in (_ADV_IND, _ADV_DIRECT_IND) and _UART_SERVICE_UUID in decode_services(
                adv_data
            ):
                # Found a potential device, remember it and stop scanning.
                self._addr_type = addr_type
                self._addr = bytes(
                    addr
                )  # Note: addr buffer is owned by caller so need to copy it.
                self._name = decode_name(adv_data) or "?"
                self._ble.gap_scan(None)

        elif event == _IRQ_SCAN_DONE:
            if self._scan_callback:
                if self._addr:
                    # Found a device during the scan (and the scan was explicitly stopped).
                    self._scan_callback(self._addr_type, self._addr, self._name)
                    self._scan_callback = None
                else:
                    # Scan timed out.
                    self._scan_callback(None, None, None)

        elif event == _IRQ_PERIPHERAL_CONNECT:
            # Connect successful.
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                self._conn_handle = conn_handle
                self._ble.gattc_discover_services(self._conn_handle)

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            # Disconnect (either initiated by us or the remote end).
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                # If it was initiated by us, it'll already be reset.
                self._reset()

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service.
            conn_handle, start_handle, end_handle, uuid = data
            print("service", data)
            if conn_handle == self._conn_handle and uuid == _UART_SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle

        elif event == _IRQ_GATTC_SERVICE_DONE:
            # Service query complete.
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(
                    self._conn_handle, self._start_handle, self._end_handle
                )
            else:
                print("Failed to find uart service.")
                self._reset()

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle == self._conn_handle and uuid == _UART_RX_CHAR_UUID:
                self._rx_handle = value_handle
            if conn_handle == self._conn_handle and uuid == _UART_TX_CHAR_UUID:
                self._tx_handle = value_handle

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            # Characteristic query complete.
            if self._tx_handle is not None and self._rx_handle is not None:
                # We've finished connecting and discovering device, fire the connect callback.
                if self._conn_callback:
                    self._conn_callback()
            else:
                print("Failed to find uart rx characteristic.")

        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            print("TX complete")

        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            if conn_handle == self._conn_handle and value_handle == self._tx_handle:
                if self._notify_callback:
                    self._notify_callback(notify_data)

    # Returns true if we've successfully connected and discovered characteristics.
    def is_connected(self):
        return (
            self._conn_handle is not None
            and self._tx_handle is not None
            and self._rx_handle is not None
        )

    # Find a device advertising the environmental sensor service.
    def scan(self, callback=None):
        self._addr_type = None
        self._addr = None
        self._scan_callback = callback
        self._ble.gap_scan(2000, 30000, 30000)

    # Connect to the specified device (otherwise use cached address from a scan).
    def connect(self, addr_type=None, addr=None, callback=None):
        self._addr_type = addr_type or self._addr_type
        self._addr = addr or self._addr
        self._conn_callback = callback
        if self._addr_type is None or self._addr is None:
            return False
        self._ble.gap_connect(self._addr_type, self._addr)
        return True

    # Disconnect from current device.
    def disconnect(self):
        if self._conn_handle is None:
            return
        self._ble.gap_disconnect(self._conn_handle)
        self._reset()

    # Send data over the UART
    def write(self, v, response=False):
        if not self.is_connected():
            return
        self._ble.gattc_write(self._conn_handle, self._rx_handle, v, 1 if response else 0)

    # Set handler for when data is received over the UART.
    def on_notify(self, callback):
        self._notify_callback = callback

def RelayOnAndDispChange(pin,onoff:bool , wired:bool=False):
    global g_FACE_NUMBER
    if wired:
        tmp_g_Button_idx=g_BUTTON_gpio_Cen.index(pin)
    else:
        tmp_g_Button_idx=g_BUTTON_gpio.index(pin)

    print(pin,tmp_g_Button_idx,onoff)
    g_LEDPWM[tmp_g_Button_idx].value(onoff)
    if onoff:
        #まず加減算またはリセット
        g_FACE_NUMBER=valueAddSub1(g_FACE_NUMBER,_BUTTON_TYPE_VAL[tmp_g_Button_idx]) #加算

        print("{:>2}".format(g_FACE_NUMBER))
        #g_MAX7219_DispData=_BUTTON_TYPE[tmp_g_Button_idx]+" "*1+str("{:>2}".format(g_FACE_NUMBER))+_FACE_LIST[g_FACE_NUMBER]
        g_OLED_DispData=_BUTTON_TYPE[tmp_g_Button_idx]+" "*1+str("{:>2}".format(g_FACE_NUMBER))
        g_OLED.dispStr(g_OLED_DispData,dispImmidiate=False ,clearDisp=True )
        g_OLED_DispData=_FACE_LIST[g_FACE_NUMBER]
        g_OLED.dispStr(g_OLED_DispData,y=16,dispImmidiate=True  ,clearDisp=False )
        #print(g_MAX7219_DispData)

    else:
        print("OFF==",pin,tmp_g_Button_idx,onoff)
        g_OLED_DispData=" "*1+str("{:>2}".format(g_FACE_NUMBER))
        g_OLED.dispStr(g_OLED_DispData,dispImmidiate=False ,clearDisp=True )
        g_OLED_DispData=_FACE_LIST[g_FACE_NUMBER]
        g_OLED.dispStr(g_OLED_DispData,y=16,dispImmidiate=True  ,clearDisp=False )

def multipurposeDispChange(msg:str):
    tmp_msg=msg[0:8]
    g_OLED.dispStr(tmp_msg,dispImmidiate=True  ,clearDisp=True )


def demo():
    #必ず顔設定を初期化する
    if g_onFirstTime:
        multipurposeDispChange("B.T.MODE")
        time.sleep_ms(5000)
        RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=True)
        time.sleep_ms(350)
        RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=False)
        time.sleep_ms(150)

    global g_LEDHBData
    global g_BUTTONData

    ble = bluetooth.BLE()
    central = BLESimpleCentral(ble)

    not_found = False

    try: #失敗するならTry-except-finally節は消す
        def on_scan(addr_type, addr, name):
            if addr_type is not None:
                print("Found peripheral:", addr_type, addr, name)
                central.connect()
            else:
                nonlocal not_found
                not_found = True
                print("No peripheral found.")
        while True:
            tmp_ButtonData=[False,0,True,0]
        
            central.scan(callback=on_scan)

            # Wait for connection...
            while not central.is_connected():
                time.sleep_ms(100)
                if not_found:
                    return

            print("Connected")
            multipurposeDispChange("Connect.")
            time.sleep_ms(1000)

            def on_rx(v):
                global g_BUTTONData
                global g_LEDHBData
                #データ受けたとき。つまりButton側から何か来たとき。
                data=struct.unpack("<HBH",v)
                print("RX", v,data)
                #Dataの2個目を見て、0ならHeart-Beat。それ以外かつPIn番号一致ならば出力処理。
                if data[1]==0 and data[2]==0:
                    g_LEDHBData=True
                else:
                    try:
                        g_BUTTONData=[True,data[1],True,data[2]]
                        print (g_BUTTONData)
                    except:
                        pass


            central.on_notify(on_rx)

            with_response = False

            i = 0
            #タイマー処理
            basetime=time.ticks_ms()
            #タイマーループ変数処理用
            time_of_next_keys=["Bluetooth","Button","HeartBeat"]
            time_of_next_value=0
            time_of_basetime_reset=2**16
            time_of_next_dict=dict.fromkeys(time_of_next_keys,time_of_next_value)
            #次のTickタイミングを決める
            time_of_next_dict["Bluetooth"]=5000
            time_of_next_dict["Button"]=500
            time_of_next_dict["HeartBeat"]=500

            while central.is_connected():
                #ズレを個々で計算するのはやめて一括計算。差が大きくなったら取りなおし
                #と思ったけど個々に処理した方が圧倒的に扱いやすい？
                basediff=time.ticks_diff(time.ticks_ms(),basetime)
                if basediff > (time_of_basetime_reset) : 
                    basetime=time.ticks_ms()
                    basediff=time.ticks_diff(time.ticks_ms(),basetime)
                    #各ループ積算もリセット
                    time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+5000)
                    time_of_next_dict["Button"]=time.ticks_add(basediff,+500)
                    time_of_next_dict["HeartBeat"]=time.ticks_add(basediff,+500)
                #print(basetime,basediff,time_of_next_dict)

                #HeartBeatの検出時
                if g_LEDHBData :
                    g_LEDHB.on()
                    print(basediff,g_LEDHB.value(),g_LEDHBData)
                    g_LEDHBData=False
                    time_of_next_dict["HeartBeat"]=time.ticks_add(basediff,+2000)
                if time.ticks_diff(time_of_next_dict["HeartBeat"],basediff)<=0:
                    g_LEDHB.off()
                    time_of_next_dict["HeartBeat"]=time.ticks_add(basediff,+time_of_basetime_reset)

                #ボタン情報の検出時
                if g_BUTTONData[0]:
                    if not tmp_ButtonData[0]:
                        tmp_ButtonData=g_BUTTONData[:]
                        g_BUTTONData=[False,0,True,0]
                        RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=True)
                        time_of_next_dict["Button"]=time.ticks_add(basediff,+450)
                if time.ticks_diff(time_of_next_dict["Button"],basediff)<=100:
                    if tmp_ButtonData[0]:
                        RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=False)
                if time.ticks_diff(time_of_next_dict["Button"],basediff)<=0:
                    tmp_ButtonData=[False,0,True,0]

                #Bluetooth送信処理(HeartBeat)
                try:
                    #死活監視メッセージを定期的にButtonに送る。
                    #LEDも定期的に更新する。(予定)
                    if time.ticks_diff(time_of_next_dict["Bluetooth"],basediff)<=0:
                        v = struct.pack("<HBH",basediff>>16,0,basediff&(2**16-1))
                        print("TX", v)
                        central.write(v, with_response)
                        time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+5000)
                except:
                    print("TX failed")
                i += 1
                #wait処理(汎用、BLE待ち)
                #time.sleep_ms(400 if with_response else 30)
                #print (basediff,g_LEDHBData,g_BUTTONData)
                time.sleep_ms(1)

            print("Disconnected")
            multipurposeDispChange("Dis-Conn")
            central._ble.active(False)
            time.sleep_ms(3000)
            central._ble.active(True)
    finally: #失敗するならTry-except-finally節は消す
        #とりあえずBLEの再起動できるかテスト
        central._ble.active(False)
        time.sleep_ms(3000)
        central._ble.active(True)
        #central._reset()
        

def init_():
    #MAX7219 SPI設定
    #global g_MAX7219
    global g_OLED
    global g_WIRED
    global g_BUTTON
    global g_LEDPWM
    global g_LEDHB
    #spi=SPI(0,baudrate=100_000,polarity=1, phase=0, sck=Pin(g_MAX7219_gpio["SCK"]), mosi=Pin(g_MAX7219_gpio["MOSI"]), miso=Pin(g_MAX7219_gpio["MISO"]))
    i2c=I2C(0, sda=pin(g_OLED_gpio["SDA"]), scl=pin(g_OLED_gpio["SCL"]), freq=1_000_000)
    #ss=Pin(g_MAX7219_gpio["CS"],Pin.OUT)
    tmp=Ssd1306_i2c_JAFont(i2c,i2c_id=0x3c,128,y=32)
    g_OLED=tmp
    g_OLED.dispStr("INIT",fsize=4)
    g_OLED.setDefaultFsize(2)


    #ボタンの初期化
    for i in g_BUTTON_gpio_Cen:
        tmp=DebouncedInput(i, btn_callback, pin_pull=Pin.PULL_UP,pin_logic_pressed=False)
        g_BUTTON.append(tmp)
    #LEDPWMの初期化
    for i in g_LEDPWM_gpio:
        tmp2=Pin(i,mode=Pin.OUT,value=False)
        tmp=Signal(tmp2, invert=True)
        tmp.off()
        g_LEDPWM.append(tmp)
    #LED HBの初期化
    tmp=Pin(g_LEDHB_gpio[0],mode=Pin.OUT,value=False)
    g_LEDHB=tmp
    #ワイヤードの初期化
    tmp=Pin(g_WIRED_gpio[0],mode=Pin.IN,pull=Pin.PULL_UP)
    g_WIRED=tmp

###############################################
#ここから有線モードの処理
###############################################

def demo_btn():
    global g_LEDHBData
    global g_BUTTONData
    #初期起動の処理

    multipurposeDispChange("LINEMODE")   
    time.sleep_ms(5000)
    RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=True)
    time.sleep_ms(350)
    RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=False)
    time.sleep_ms(150)            
    multipurposeDispChange("LINE--go")                          
    #とりあえず今はボタンアクションのみ
    while True:
        #ボタン情報の検出時
        if g_BUTTONData[0]:
            tmp_ButtonData=g_BUTTONData[:]
            g_BUTTONData=[False,0,True,0]
            if tmp_ButtonData[2]==False :
                RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=False,wired=True)
                if tmp_ButtonData[3]<=150:
                    time.sleep_ms(151- tmp_ButtonData[3])
                RelayOnAndDispChange(pin=g_BUTTON_gpio[0],onoff=False)
                RelayOnAndDispChange(pin=g_BUTTON_gpio[1],onoff=False)
                RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=False)


            if tmp_ButtonData[2]==True :
                RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=True,wired=True)
                if tmp_ButtonData[3]<=350:
                    time.sleep_ms(351- tmp_ButtonData[3])   
            tmp_ButtonData=[False,0,True,0]
        time.sleep_ms(1)
        #RelayOnAndDispChange(pin=tmp_ButtonData[0],onoff=False)
        #RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=False)
        #RelayOnAndDispChange(pin=tmp_ButtonData[2],onoff=False)



###############################################
#ここまで有線モードの処理
###############################################


if __name__ == "__main__":
    g_onFirstTime=True
    init_()
    #有線か無線かを判断
    time.sleep_ms(100)
    i=0
    j=0
    while i<2000:
        i=i+1
        time.sleep_ms(1)
        if not g_WIRED.value():
            j=j+1
    while True:
        if j>=1000: #有線と判定
            print ("Wired mode",j)
            demo_btn()
            g_onFirstTime=False

        else:
            print ("BLE mode",j)
            demo()
            g_onFirstTime=False
