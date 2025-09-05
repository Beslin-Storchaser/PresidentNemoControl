# This example demonstrates a UART periperhal.
# based from https://github.com/micropython/micropython/blob/master/examples/bluetooth/ble_simple_peripheral.py
# President Nemo controller-side for Raspberry Pi Pico w.

import bluetooth
import random
import struct
import time
from machine import Pin,PWM,ADC,freq

# 上記参考URLからble_advertising.pyを入手し、Pi Picoのmain.pyと同じフォルダに置く。
from ble_advertising import advertising_payload
# updebouncein : https://github.com/jmcclin2/updebouncein/blob/main/debounced_input.py
# ここからdebounced_input.pyをPi Picoのmain.pyと同じフォルダに置く。
from debounced_input import DebouncedInput          
from micropython import const

freq(75_000_000)    #Pi Picoの動作周波数を減らす。消費電力減少効果。
# Bluetooth/BLE関係の定数
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)
# Bluetooth/BLE関係の定数　おわり



##ボタン等の初期グローバル変数宣言
#バッテリーの電圧基準。乾電池2本時。
#LOW以下：赤、LOW-MID：緑、MID以上：青。
_BATT_THRESHOLD_LOW=2.1
_BATT_THRESHOLD_MID=2.6
#乾電池3本の時は以下を使う。
#_BATT_THRESHOLD_LOW=3.6
#_BATT_THRESHOLD_MID=4.2
#充電池2本の時は以下を使う。
#_BATT_THRESHOLD_LOW=2.0
#_BATT_THRESHOLD_MID=2.4

###ボタン等の初期グローバル変数宣言
# 各入出力のGPIO番号
g_BUTTON_gpio=(0,2,4)    #Button 
g_LEDPWM_gpio=(1,3,5)    #LED-btn
g_LEDHB_gpio=(20,)       #LED-HeartBeat for BLE
g_LEDBATT_gpio=(8,7,6)   #LED-PWR
g_BATTVOLT_gpio=(26,)    #Battery Voltage=GPIO26で読む
_BATT_ADC_R1=200_000     #電池電圧測定ポイントの分圧抵抗R1。単位オーム。+側
_BATT_ADC_R2=100_000     #電池電圧測定ポイントの分圧抵抗R2。単位オーム。GND側
_BATT_ADC_factor=(1/(_BATT_ADC_R2/(_BATT_ADC_R1+_BATT_ADC_R2)))*3.3/(2**16)     #ADC入力値と分圧比から電池電圧を計算するための比率計算。

#for debounce_input callback
g_BUTTONData=[False,0,True,0]   #data valid/invalid, Pin No, Push /not push, dulation
# 各入出力のオブジェクト保存用グローバル変数。
g_BUTTON=[]
g_LEDPWM=[]
g_LEDHB=0
g_LEDHBData=[]
g_LEDBATT=[]
g_BATTVOLT=0



###ボタン押し下げ時のコールバック関数。同時押しは考慮していない。
def btn_callback(pin, pressed, duration_ms):
    global g_BUTTONData
    if (pressed):
        print("Pin-", pin, " Pressed:", duration_ms, "ms since last press")
        g_BUTTONData=[True,pin,True,duration_ms]
    if (pressed==False):
        print("Pin-", pin, " released:", duration_ms, "ms long press ")
        g_BUTTONData=[True,pin,False,duration_ms]


###Bluetooth UARTの入出力(Rx,Tx)のUUID設定。
# https://monomonotech.jp/kurage/webbluetooth/uuid.html
# このURLを参考にGUIDをそれぞれ新規設定して下さい。
# なお、この値はセントラル側(コントローラーの入力を受ける側)で同じ値を設定すること。
# 現在の設定値はNordic UART Service(NUS)の値と同じ。
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

###Bluetooth BLE Peripheralデバイスのクラス設定。参考元の内容そのまま。
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

#メインプロセス。BLE接続時に使用される。
#有線接続の時はここはただの電池食い。
def BLEBtn():
    #読み書きするグローバル変数の宣言
    global g_BUTTONData
    global g_LEDHBData
    #Bluetooth BLEの有効化
    ble = bluetooth.BLE()
    #何かエラーが起こったらBLEを終了するためのTry-(catch)-finally節。大抵BLE接続が切れたときに発生。
    try:
        #Bluetooth BLEのUARTサービス定義及び開始
        p = BLESimplePeripheral(ble)
        
        #データを受けたときの処理をする関数の定義
        def on_rx(v):
            # 受け取ったデータを分解してタプルとして変数に代入。
            g_LEDHBData=struct.unpack("<HBH",v)
            #DEBUG
            print("RX:", v, g_LEDHBData)
            # データを受け取ったことを示すHeart-beat LEDを点灯。
            g_LEDHB.on()
            
        #データを受けたときの処理をする関数をBluetooth BLEのUARTサービスに設定し、データが来たら呼んでもらうようセット。
        p.on_write(on_rx)

        #時間の初期値をセット。以降ここから減算してタイミングを取る。実は未使用…のはず。
        i = 0
        
        #時間の初期値をセット。この値と現在時刻とを比較して経過時間を計る。
        basetime=time.ticks_ms()
        #タイマーループ変数処理用(次の実行時間までの間隔[ms]保存用)のdict型生成。
        time_of_next_keys=["Bluetooth","Battery"]
        time_of_next_value=0
        time_of_next_dict=dict.fromkeys(time_of_next_keys,time_of_next_value)
        #次のTickタイミングを決める。単位[ms]・・・ここの値に意味は今は無い。
        #Bluetooth Heart-beat(生存確認)
        time_of_next_dict["Bluetooth"]=5000
        #電池電圧測定
        time_of_next_dict["Battery"]=5000

        # 電池容量LEDの点灯/消灯を示す変数の初期化
        battLED=False        
        # ボタンデータの一時保存先を初期化
        tmp_ButtonData=[False,0,False,0]
        # Bluetooth UART送信時のデータ保存先を初期化
        btData=[0,0,0] #現Tick、Pin番号、押し時間
        # 1秒待機
        time.sleep_ms(1000)
        
        ###　ここより無限ループ開始。
        ### このループで、ボタンの押し下げ状態の監視、電池容量LEDの点灯/消灯、Bluetoothデータの送信を行う。
        
        while True:
            
            ## 基準開始時間からのずれを計算。
            #このずれ値を各所で使用。
            basediff=time.ticks_diff(time.ticks_ms(),basetime)
            #ずれ値が一定値(60000ms)を超えたら、基準開始時間を更新。仕様上2**28ms(約3日)は更新不要なようだが、1分ごとに更新するように設定。
            if basediff > 60000 : 
                basetime=time.ticks_ms()
                basediff=time.ticks_diff(time.ticks_ms(),basetime)
                #各ループタイミングも強制リセット
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
            #電池電圧測定、HB-LED消灯、電池容量LED点灯。
            #現在の条件は5秒ごとに測定、その0.5秒後に消灯。
            if time.ticks_diff(time_of_next_dict["Battery"],basediff)<=0:
                g_LEDHB.off()
                #g_BATTVOLT_sens.on()
                battVoltage=g_BATTVOLT.read_u16() *_BATT_ADC_factor
                #g_BATTVOLT_sens.off()
                #DEBUG
                print(time.ticks_diff(time_of_next_dict["Battery"],basediff),battVoltage,battLED)

                #電池容量LEDが点灯中なら全て消灯し、5秒後に測定するようセット
                if battLED:
                    g_LEDBATT[0].off()
                    g_LEDBATT[1].off()
                    g_LEDBATT[2].off()     
                    time_of_next_dict["Battery"]=time.ticks_add(basediff,+5000)
                    battLED=False
                    print(time.ticks_diff(time_of_next_dict["Battery"],basediff),battVoltage,battLED)
                #電池容量LEDが消灯中なら電池電圧に応じたLEDを点灯。0.5秒後に消灯するようセット。               
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

            #もしボタンデータがあればそれをセットし、押した後なら即時送信体制にする。
            #グローバル変数 g_BUTTONData[0]がTrueならデータが入っているためそこを監視。
            if g_BUTTONData[0] :
                #データを一時変数にコピー
                tmp_ButtonData=g_BUTTONData[:]
                #debug#
                print(tmp_ButtonData)
                #グローバル変数を初期化し、次の入力に備える。
                g_BUTTONData=[False,0,True,0]
                #ボタン押し下げ時に、対応するLEDを付ける。
                if tmp_ButtonData[2]==True:
                    g_LEDPWM[0].off()
                    g_LEDPWM[1].off()
                    g_LEDPWM[2].off()
                    g_LEDPWM[g_BUTTON_gpio.index(tmp_ButtonData[1])].on()
                #ボタンリリース時はLEDを消灯し、Bluetooth送信用データを生成、直ぐにデータ送信するよう送信タイミングを変更。
                if tmp_ButtonData[2]==False:
                    g_LEDPWM[0].off()
                    g_LEDPWM[1].off()
                    g_LEDPWM[2].off()
                    # 現在の基準時間からのずれ量、押されたボタンのピン番号、押し下げ時間(dulation)をセット。
                    btData=[basediff,tmp_ButtonData[1],tmp_ButtonData[3]]
                    # 押し下げ時間が0ないし2**16-1(=65535)以上にならないよう閾値処理
                    if btData[2]==0 : btData[2]=500
                    if btData[2]>=(-1+2**16) : btData[2]=(-1+2**16)
                    print(btData)
                    #Bluetooth UART即時送信体制に変更のため、次の送信時刻を変更。
                    time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+0)
                #一時変数を初期化。
                tmp_ButtonData=[False,0,True,0]
            
            #Bluetooth UARTデータの送信。
            #ここが実行されるのは、Heart-beatタイミングまたはBluetoothデータ即時送信体制になったとき。
            if time.ticks_diff(time_of_next_dict["Bluetooth"],basediff)<=0:
                #Bluetooth送信データのDEBUG
                print(time.ticks_diff(time_of_next_dict["Bluetooth"],basediff))
                print("Bluetooth:",btData)
                print(struct.pack("<HBH",btData[0],btData[1],btData[2]))
                #次のBluetooth Heart-beatタイミングをセット
                time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+5000)
                #Bluetooth BLEが接続されていたら送信する。
                if p.is_connected():
                    #データを送る処理
                    # Short burst of queued notifications.
                    # データをバイト列にパックし通信量削減。
                    data = struct.pack("<HBH",btData[0],btData[1],btData[2])
                    print("TX:", data)
                    # Bluetooth UART データ送信
                    p.send(data)
                    # Bluetooth UART データ送信後の変数初期化
                    btData=[0,0,0]


            #1000us休む。その後無限ループの最初に戻る。
            time.sleep_us(1000)
    #エラーが発生するなどでエラーが出たらBLEを停止する。その後メイン関数の無限ループで復帰する。
    finally:
        ble.active(False)
        
#各入出力の初期化
def init():
    #保存対象のグローバル変数を宣言。
    global g_BUTTON
    global g_LEDPWM
    global g_LEDHB
    global g_LEDBATT
    global g_BATTVOLT
    

    #ボタンを初期化しグローバル変数に保存(配列として追加)。debouncedInputを使用。
    for i in g_BUTTON_gpio:
        tmp=DebouncedInput(i, btn_callback, pin_pull=Pin.PULL_UP,pin_logic_pressed=False)
        g_BUTTON.append(tmp)
    #LEDPWMを初期化しグローバル変数に保存。
    for i in g_LEDPWM_gpio:
        tmp=Pin(i,mode=Pin.OUT,value=False)
        g_LEDPWM.append(tmp)
    #LED HBを初期化しグローバル変数に保存。
    tmp=Pin(g_LEDHB_gpio[0],mode=Pin.OUT,value=False)
    g_LEDHB=tmp
    #LED Batteryを初期化しグローバル変数に保存。
    for i in g_LEDBATT_gpio:
        tmp=Pin(i,mode=Pin.OUT,value=False)
        g_LEDBATT.append(tmp)
    #バッテリー電圧読み出し機構を初期化しグローバル変数に保存。
    tmp=ADC(Pin(g_BATTVOLT_gpio[0], mode=Pin.IN))
    g_BATTVOLT=tmp
    pass

#main関数。初期化とメインプロセスの無限起動をしている。
if __name__ == "__main__":
    #初期化
    init()
    #メインプロセスの呼び出し無限ループ
    while True:
        BLEBtn()

