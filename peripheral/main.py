# This example demonstrates a UART periperhal.

# This example demonstrates the low-level bluetooth module. For most
# applications, we recommend using the higher-level aioble library which takes
# care of all IRQ handling and connection management. See
# https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble

import bluetooth
import random
import struct
import time
from machine import Pin,PWM,ADC,freq
from ble_advertising import advertising_payload
from debounced_input import DebouncedInput
from micropython import const

freq(75_000_000)
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

##ボタン等の初期グローバル変数宣言
#バッテリーの電圧基準。乾電池2本時。
#LOW以下：赤、LOW-MID：緑、MID以上：青を予定。
_BATT_THRESHOLD_LOW=2.1
_BATT_THRESHOLD_MID=2.6
#乾電池3本の時は以下を使う。
#_BATT_THRESHOLD_LOW=3.6
#_BATT_THRESHOLD_MID=4.2
#充電池2本の時は以下を使う。
#_BATT_THRESHOLD_LOW=2.0
#_BATT_THRESHOLD_MID=2.4

g_BUTTON_gpio=(0,2,4)       #Button 
g_LEDPWM_gpio=(1,3,5)    #LED-btn
g_LEDHB_gpio=(20,)           #LED-HeartBeat for BLE
g_LEDBATT_gpio=(8,7,6)   #LED-PWR
g_BATTVOLT_gpio=(26,)        #Battery Voltage=GPIO26で読む
_BATT_ADC_R1=200_000
_BATT_ADC_R2=100_000
_BATT_ADC_factor=(1/(_BATT_ADC_R2/(_BATT_ADC_R1+_BATT_ADC_R2)))*3.3/(2**16)

g_BUTTONData=[False,0,True,0]   #for debounce_input callback
g_BUTTON=[]
g_LEDPWM=[]
g_LEDHB=0
g_LEDHBData=[]
g_LEDBATT=[]
g_BATTVOLT=0


##ボタン等の初期グローバル変数宣言おわり

##ボタン押し下げ時のコールバック関数
def btn_callback(pin, pressed, duration_ms):
    global g_BUTTONData
    if (pressed):
        print("Pin-", pin, " Pressed:", duration_ms, "ms since last press")
        g_BUTTONData=[True,pin,True,duration_ms]
    if (pressed==False):
        print("Pin-", pin, " released:", duration_ms, "ms long press ")
        g_BUTTONData=[True,pin,False,duration_ms]



_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX = (
    bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_UART_RX = (
    bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
    _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)
_UART_SERVICE = (
    _UART_UUID,
    (_UART_TX, _UART_RX),
)


class BLESimplePeripheral:
    def __init__(self, ble, name="BLE_btn"):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services((_UART_SERVICE,))
        self._connections = set()
        self._write_callback = None
        self._payload = advertising_payload(name=name, services=[_UART_UUID])
        self._advertise()

    def _irq(self, event, data):
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            print("New connection", conn_handle)
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            print("Disconnected", conn_handle)
            self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            value = self._ble.gatts_read(value_handle)
            if value_handle == self._handle_rx and self._write_callback:
                self._write_callback(value)

    def send(self, data):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle_tx, data)

    def is_connected(self):
        return len(self._connections) > 0

    def _advertise(self, interval_us=500000):
        print("Starting advertising")
        self._ble.gap_advertise(interval_us, adv_data=self._payload)


    def on_write(self, callback):
        self._write_callback = callback

#BLEを使うときの関数
def BLEBtn():
    global g_BUTTONData
    global g_LEDHBData
    ble = bluetooth.BLE()
    try:
        p = BLESimplePeripheral(ble)
        
        #データを受けたときの処理
        def on_rx(v):
            g_LEDHBData=struct.unpack("<HBH",v)
            print("RX:", v, g_LEDHBData)
            g_LEDHB.on()
            

        p.on_write(on_rx)

        i = 0
        #時間の初期値をセット。以降ここから減算してタイミングを取る

        basetime=time.ticks_ms()
        #タイマーループ変数処理用
        time_of_next_keys=["Bluetooth","Battery"]
        time_of_next_value=0
        time_of_next_dict=dict.fromkeys(time_of_next_keys,time_of_next_value)
        #次のTickタイミングを決める
        time_of_next_dict["Bluetooth"]=5000
        time_of_next_dict["Battery"]=5000

 
        battLED=False        
        tmp_ButtonData=[False,0,False,0]
        btData=[0,0,0] #現Tick、Pin番号、押し時間

        time.sleep_ms(1000)
        while True:
            

            
            
            #ズレを個々で計算するのはやめて一括計算。差が大きくなったら取りなおし
            #と思ったけど個々に処理した方が圧倒的に扱いやすい？
            basediff=time.ticks_diff(time.ticks_ms(),basetime)
            if basediff > 60000 : 
                basetime=time.ticks_ms()
                basediff=time.ticks_diff(time.ticks_ms(),basetime)
                #各ループ積算もリセット
                time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+5000)
                time_of_next_dict["Battery"]=time.ticks_add(basediff,+500)
            #print(basetime,basediff,time_of_next_dict)
            #処理する内容群
            '''
            #ボタン情報の送信（Global変数を読んでデータを確認し送信）
            #＜ボタンと対応するLED点灯は割り込み関数内で処理する。＞
            #＜ボタン出力-セントラル直結は結線+SBDで対応済み＞
            #電池電圧測定と対応するLED点灯（1~5秒ごと）
            #定期的にデータを送る/受ける処理（受けは割り込み。送信は5~10秒ごと）
            '''
            #電池電圧測定/HB-LED無効
            if time.ticks_diff(time_of_next_dict["Battery"],basediff)<=0:
                g_LEDHB.off()
                #g_BATTVOLT_sens.on()
                battVoltage=g_BATTVOLT.read_u16() *_BATT_ADC_factor
                #g_BATTVOLT_sens.off()
                print(time.ticks_diff(time_of_next_dict["Battery"],basediff),battVoltage,battLED)


                if battLED:
                    g_LEDBATT[0].off()
                    g_LEDBATT[1].off()
                    g_LEDBATT[2].off()     
                    time_of_next_dict["Battery"]=time.ticks_add(basediff,+5000)
                    battLED=False
                    print(time.ticks_diff(time_of_next_dict["Battery"],basediff),battVoltage,battLED)
                else:
                    battLED=True
                    time_of_next_dict["Battery"]=time.ticks_add(basediff,+500)
                    if battVoltage<_BATT_THRESHOLD_LOW :
                        g_LEDBATT[0].on()
                        g_LEDBATT[1].off()
                        g_LEDBATT[2].off()
                    elif battVoltage<_BATT_THRESHOLD_MID :
                        g_LEDBATT[0].off()
                        g_LEDBATT[1].on()
                        g_LEDBATT[2].off()
                    else :
                        g_LEDBATT[0].off()
                        g_LEDBATT[1].off()
                        g_LEDBATT[2].on()
                    print(time.ticks_diff(time_of_next_dict["Battery"],basediff),battVoltage,battLED)

            #もしボタンデータがあればそれをセットし、押した後なら即時送信体制に
            if g_BUTTONData[0] :
                tmp_ButtonData=g_BUTTONData[:]
                #debug#
                print(tmp_ButtonData)
                g_BUTTONData=[False,0,True,0]
                #ボタン押し下げ時。LEDを付ける。
                if tmp_ButtonData[2]==True:
                    g_LEDPWM[0].off()
                    g_LEDPWM[1].off()
                    g_LEDPWM[2].off()
                    g_LEDPWM[g_BUTTON_gpio.index(tmp_ButtonData[1])].on()
                #ボタンリリース時
                if tmp_ButtonData[2]==False:
                    g_LEDPWM[0].off()
                    g_LEDPWM[1].off()
                    g_LEDPWM[2].off()
                    btData=[basediff,tmp_ButtonData[1],tmp_ButtonData[3]]
                    if btData[2]==0:btData[2]=500
                    if btData[2]>=(-1+2**16):btData[2]=(-1+2**16)
                    print(btData)
                    time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+0)
                tmp_ButtonData=[False,0,True,0]
            
            if time.ticks_diff(time_of_next_dict["Bluetooth"],basediff)<=0:
                #Bluetooth送信
                print(time.ticks_diff(time_of_next_dict["Bluetooth"],basediff))
                print("Bluetooth:",btData)
                print(struct.pack("<HBH",btData[0],btData[1],btData[2]))
                time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+5000)
                if p.is_connected():
                    #データを送る処理
                    # Short burst of queued notifications.

                    data = struct.pack("<HBH",btData[0],btData[1],btData[2])
                    print("TX:", data)
                    p.send(data)
                    btData=[0,0,0]


            #1000us休む
            time.sleep_us(1000)
    finally:
        ble.active(False)
        
#初期化
def init():
    global g_BUTTON
    global g_LEDPWM
    global g_LEDHB
    global g_LEDBATT
    global g_BATTVOLT
    

    #ボタンの初期化
    for i in g_BUTTON_gpio:
        tmp=DebouncedInput(i, btn_callback, pin_pull=Pin.PULL_UP,pin_logic_pressed=False)
        g_BUTTON.append(tmp)
    #LEDPWMの初期化
    for i in g_LEDPWM_gpio:
        tmp=Pin(i,mode=Pin.OUT,value=False)
        g_LEDPWM.append(tmp)
    #LED HBの初期化
    tmp=Pin(g_LEDHB_gpio[0],mode=Pin.OUT,value=False)
    g_LEDHB=tmp
    #LED Batteryの初期化
    for i in g_LEDBATT_gpio:
        tmp=Pin(i,mode=Pin.OUT,value=False)
        g_LEDBATT.append(tmp)
    #バッテリー読み出し機構の初期化
    tmp=ADC(Pin(g_BATTVOLT_gpio[0], mode=Pin.IN))
    g_BATTVOLT=tmp
    pass

if __name__ == "__main__":
    init()
    while True:
        BLEBtn()
