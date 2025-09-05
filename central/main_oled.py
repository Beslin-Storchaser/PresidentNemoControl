# This example finds and connects to a peripheral running the
# UART service (e.g. ble_simple_peripheral.py).
# President Nemo display-side(Central) for Raspberry Pi Pico w.
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
#OLED用ライブラリのインポート。OLEDの機種によって変更する。大抵の安いのはこれで動くと思う。
#このライブラリは別途ダウンロードしてRaspberry Pi Pico Wにコピー（配置）しておく。
from ssd1306_i2c_JAFont import Ssd1306_i2c_JAFont
from debounced_input import DebouncedInput

# 上記参考URLからble_advertising.pyを入手し、Pi Picoのmain.pyと同じフォルダに置く。
from ble_advertising import decode_services, decode_name

from micropython import const

# Bluetooth/BLE関係の定数
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

###Bluetooth UARTの入出力(Rx,Tx)のUUID設定。
#この値はペリフェラル側(コントローラー側)と同じUUID値をセットする。
_UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX_CHAR_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_RX_CHAR_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

# Bluetooth/BLE関係の定数　おわり


#基本はButtonと情報(Pin番号他)を共通化。
g_BUTTON_gpio=(0,2,4)       #Button コントローラー側(peripheral)と一致する必要がある。コントローラ側での入力の識別用。
g_BUTTON_gpio_Cen=(7,6,5)   #Button　有線時に使用。
g_LEDPWM_gpio=(10,11,12)    #Central側はリレー出力として使用。
g_LEDHB_gpio=(15,)          #LED-HeartBeat for BLE
g_WIRED_gpio=(4,)           #有線無線判定。プルアップ。GNDなら有線。

#for debounce_input callback
g_BUTTONData=[False,0,True,0]   #data valid/invalid, Pin No, Push /not push, dulation
# 各入出力のオブジェクト保存用グローバル変数。
g_BUTTON=[]
g_LEDPWM=[]
g_LEDHB=0
g_LEDHBData=[]
g_WIRED=0

#OLED(i2c通信）設定-SCL,SDA
g_OLED_gpio={
    "SCL":1,    #SCL
    "SDA":0,    #SDA

}
g_OLED=0
g_OLED_DispData=" "*8

#_BUTTON_TYPE=('A','D','R') #ボタンタイプ
_BUTTON_TYPE=('Add','Down','Res') #ボタンタイプ。それぞれ「次へ進む」「一つ戻る」「初期値にリセット」

#ボタンタイプに対応する操作方法のをここで宣言
_BUTTON_TYPE_VAL=(1,-1,0)
# 表示する顔の情報に対応する文字列。必要に応じて変更する。
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
#最初の顔(リセット後)の番号。
g_FACE_NUMBER=1
#initialize variables
MAX_VAL_ABS=999 #現在未使用。顔が増えたときにPC無しで変更できるようにするための絶対的な上限値。
g_max_val=16    #初期値。今後ファイル読み出し対応予定。
MIN_VAL_ABS=1   #現在未使用。顔が増えたときにPC無しで変更できるようにするための絶対的な下限値。
g_min_val=MIN_VAL_ABS   #下限値。基本1。
DURATION_LONG_PRESS=2500    #長押し判定の閾値。

#電源投入直後かどうかの判定用グローバル変数。
g_onFirstTime=True

###ボタン押し下げ時のコールバック関数。同時押しは考慮していない。有線接続時のみ使用。
def btn_callback(pin, pressed, duration_ms):
    global g_BUTTONData
    if (pressed):
        print("Pin-", pin, " Pressed:", duration_ms, "ms since last press")
        g_BUTTONData=[True,pin,True,duration_ms]
    if (pressed==False):
        print("Pin-", pin, " released:", duration_ms, "ms long press ")
        g_BUTTONData=[True,pin,False,duration_ms]
   
###顔番号の増加、減少、リセット処理。最小値-1=最大値のようにリング上となるよう処理。
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
    
###Bluetooth BLE Centralデバイスのクラス設定。参考元の内容そのまま。
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

#入力に応じてリレーをOn/OFF、7セグの更新を行う。
def RelayOnAndDispChange(pin,onoff:bool , wired:bool=False):
    global g_FACE_NUMBER
    #有線接続時と無線接続時でGPIO番号が異なるのでそれぞれでどの入力が来たかでONすべきピンを特定。
    if wired:
        tmp_g_Button_idx=g_BUTTON_gpio_Cen.index(pin)
    else:
        tmp_g_Button_idx=g_BUTTON_gpio.index(pin)

    print(pin,tmp_g_Button_idx,onoff)
    #対象のリレーのON/OFF。これで表示用基板の入力端子に情報を送る。
    g_LEDPWM[tmp_g_Button_idx].value(onoff)
    #もしリレーON(=画面の切り替えが発生)したなら
    if onoff:
        #まず加減算またはリセット後の画面番号を計算
        g_FACE_NUMBER=valueAddSub1(g_FACE_NUMBER,_BUTTON_TYPE_VAL[tmp_g_Button_idx]) #加算

        print("{:>2}".format(g_FACE_NUMBER))
        #押されたボタンの情報、現在の顔番号、顔情報を表示
        g_OLED_DispData=_BUTTON_TYPE[tmp_g_Button_idx]+" "*1+str("{:>2}".format(g_FACE_NUMBER))
        g_OLED.dispStr(g_OLED_DispData,dispImmidiate=False ,clearDisp=True )
        g_OLED_DispData=_FACE_LIST[g_FACE_NUMBER]
        g_OLED.dispStr(g_OLED_DispData,y=16,dispImmidiate=True  ,clearDisp=False )
        

    else:
        print("OFF==",pin,tmp_g_Button_idx,onoff)
        #押されたボタンの情報部のみ空白、現在の顔番号、顔情報を表示

        g_OLED_DispData=" "*1+str("{:>2}".format(g_FACE_NUMBER))
        g_OLED.dispStr(g_OLED_DispData,dispImmidiate=False ,clearDisp=True )
        g_OLED_DispData=_FACE_LIST[g_FACE_NUMBER]
        g_OLED.dispStr(g_OLED_DispData,y=16,dispImmidiate=True  ,clearDisp=False )

#OLED情報更新
def multipurposeDispChange(msg:str):
    tmp_msg=msg[0:8]
    g_OLED.dispStr(tmp_msg,dispImmidiate=True  ,clearDisp=True )


#無線 Bluetooth BLE接続時のメイン関数
def demo():
    #必ず顔設定を初期化する。電源投入時のみ実行される。
    if g_onFirstTime:
        multipurposeDispChange("B.T.MODE")
        for i in range(1,6):
            multipurposeDispChange("B.T.MODE",clearDisp=True )
            multipurposeDispChange(str(6-i)+"secWait",y=16,clearDisp=False )
            time.sleep_ms(1000)
            
        #time.sleep_ms(5000)
        RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=True)
        time.sleep_ms(350)
        RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=False)
        time.sleep_ms(150)

    global g_LEDHBData
    global g_BUTTONData
    #Bluetoothを有効化、BLE Centralサービスの開始
    ble = bluetooth.BLE()
    central = BLESimpleCentral(ble)
    
    #デバイス発見状態の変数初期化
    not_found = False

    try: #失敗するならTry-except-finally節は消す
        #Bluetoothデバイススキャンのためのコールバック関数宣言
        def on_scan(addr_type, addr, name):
            if addr_type is not None:
                print("Found peripheral:", addr_type, addr, name)
                central.connect()
            else:
                nonlocal not_found
                not_found = True
                print("No peripheral found.")
        #無限ループ開始。各所のreturnで無限ループが終了し、finally節でBLEの停止/起動を行って、その後main()内で再駆動される。
        while True:
            #デバイス発見状態の変数初期化
            tmp_ButtonData=[False,0,True,0]
            #接続対象のデバイスのスキャン。見つかると接続処理が行われる
            central.scan(callback=on_scan)

            # 対象のデバイスに接続されるまで待ち。何もデバイスが無かった場合はreturn
            while not central.is_connected():
                time.sleep_ms(100)
                if not_found:
                    return
            # 対象のデバイスに接続されるとここに来る。
            print("Connected")
            #接続したことを表示。その後1秒待ち。
            multipurposeDispChange("Connect.")
            time.sleep_ms(1000)
            
            # UARTデータが来たときにデータを処理してグローバル変数のボタンデータに変換し格納するコールバック関数。
            def on_rx(v):
                global g_BUTTONData
                global g_LEDHBData
                #データ受けたとき。つまりButton側から何か来たとき。
                data=struct.unpack("<HBH",v)
                print("RX", v,data)
                #Dataの2個目と3個目を見て、どちらも0ならHeart-Beat。それ以外かつPIn番号一致ならば出力処理。
                if data[1]==0 and data[2]==0:
                    g_LEDHBData=True
                else:
                    try:
                        #ボタン状態変数に値を格納。
                        g_BUTTONData=[True,data[1],True,data[2]]
                        print (g_BUTTONData)
                    except:
                        #無効なピン番号だった場合は無視。普通はここに来ない。
                        pass

            # UARTコールバック関数をセット
            central.on_notify(on_rx)
            
            #現在未使用。
            with_response = False
            
            #未使用。
            i = 0
            #時間の初期値をセット。この値と現在時刻とを比較して経過時間を計る。
            basetime=time.ticks_ms()
            #タイマーループ変数処理用(次の実行時間までの間隔[ms]保存用)のdict型生成。
            time_of_next_keys=["Bluetooth","Button","HeartBeat"]
            time_of_next_value=0
            time_of_next_dict=dict.fromkeys(time_of_next_keys,time_of_next_value)
            #次のTickタイミングを決める。単位[ms]・・・ここの値に意味は今は無い。
            #Bluetooth Heart-beat(生存確認) button
            time_of_next_dict["Bluetooth"]=5000
            time_of_next_dict["Button"]=500
            time_of_next_dict["HeartBeat"]=500
            #基準時刻更新タイミング。単位[ms]。Peripheral側(60000ms)と同様の内容。
            time_of_basetime_reset=2**16
            while central.is_connected():
                ## 基準開始時間からのずれを計算。
                #このずれ値を各所で使用。
                basediff=time.ticks_diff(time.ticks_ms(),basetime)
                #ずれ値が一定値(65536ms)を超えたら、基準開始時間を更新。仕様上2**28ms(約3日)は更新不要なようだが、約1分ごとに更新するように設定。
                if basediff > (time_of_basetime_reset) : 
                    basetime=time.ticks_ms()
                    basediff=time.ticks_diff(time.ticks_ms(),basetime)
                    #各ループタイミングも強制リセット
                    time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+5000)
                    time_of_next_dict["Button"]=time.ticks_add(basediff,+500)
                    time_of_next_dict["HeartBeat"]=time.ticks_add(basediff,+500)
                #print(basetime,basediff,time_of_next_dict)

                #HeartBeatの検出時
                if g_LEDHBData :
                    #HeartBeatのLEDをON
                    g_LEDHB.on()
                    print(basediff,g_LEDHB.value(),g_LEDHBData)
                    g_LEDHBData=False
                    #HeartBeatの変数をリセット
                    #HeartBeatのLEDをON=False
                    #HeartBeatのLEDを2秒後に消すようセット
                    time_of_next_dict["HeartBeat"]=time.ticks_add(basediff,+2000)
                #HeartBeatのLEDを消すタイミングになったとき
                if time.ticks_diff(time_of_next_dict["HeartBeat"],basediff)<=0:
                    #HeartBeatのLEDをON
                    g_LEDHB.off()
                    #次のタイミングはg_LEDHBDataがTrueまで無いので、無効なタイミングをセット。
                    time_of_next_dict["HeartBeat"]=time.ticks_add(basediff,+time_of_basetime_reset)
                
                #ボタンデータが来たときの処理。
                #グローバル変数 g_BUTTONData[0]がTrueならデータが入っているためそこを監視。
                if g_BUTTONData[0]:
                    #一時保存したデータはリレーOFFまで必要なのでそこまで保持するための分岐。
                    if not tmp_ButtonData[0]:
                        #データを一時変数にコピー
                        tmp_ButtonData=g_BUTTONData[:]
                        #グローバル変数を初期化し、次の入力に備える。
                        g_BUTTONData=[False,0,True,0]
                        #対象のボタンと対応するリレーをONにし、顔情報を更新
                        RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=True)
                        #450ms後に一時変数をクリアするよう、タイミングをセット
                        time_of_next_dict["Button"]=time.ticks_add(basediff,+450)
                #リレーをオフするタイミング(=リレーONから350ms以上経過後)になったら
                if time.ticks_diff(time_of_next_dict["Button"],basediff)<=100:
                    #オフにすべきリレーがあるかどうか（一時変数がまだ有効か）
                    if tmp_ButtonData[0]:
                        #対象のボタンと対応するリレーをOFF
                        RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=False)
                #一時変数を消去するタイミングが来たら（リレーオフ後100ms後）        
                if time.ticks_diff(time_of_next_dict["Button"],basediff)<=0:
                    tmp_ButtonData=[False,0,True,0]

                #Bluetooth送信処理(HeartBeat)
                try:
                    #死活監視メッセージを定期的にPeripheral側に送る。送る値は適当。（Peripheral側でも何もしていない）
                    if time.ticks_diff(time_of_next_dict["Bluetooth"],basediff)<=0:
                        #basediff>>16（いまは0）、ボタン（なし）、basediffの下位16bitをデータとして送信
                        v = struct.pack("<HBH",basediff>>16,0,basediff&(2**16-1))
                        print("TX", v)
                        #Bluetooth UART 送信
                        central.write(v, with_response)
                        #次のHeart-beat BLEメッセージ送信タイミングをセット
                        time_of_next_dict["Bluetooth"]=time.ticks_add(basediff,+5000)
                except:
                    #送信失敗しても処理を続ける。
                    print("TX failed")
                #今のところ使い道無し
                i += 1
                #wait処理(汎用、BLE待ち)
                #time.sleep_ms(400 if with_response else 30)
                #print (basediff,g_LEDHBData,g_BUTTONData)
                #1ms待って次のループへ
                time.sleep_ms(1)
            ###ceontralとPeripheralとの通信が切れたときの処理
            print("Disconnected")
            #OLEDに接続切れたことを通知
            multipurposeDispChange("Dis-Conn")
            #BLEの停止/起動。その後無限ループ処理によりデバイス接続待ちに移行。
            central._ble.active(False)
            time.sleep_ms(3000)
            central._ble.active(True)
    finally: #失敗するならTry-except-finally節は消す
        #エラー発生時にとりあえずBLEの再起動できるかどうかのために設置。
        central._ble.active(False)
        time.sleep_ms(3000)
        central._ble.active(True)
        #central._reset()
        

def init_():
    #保存対象のグローバル変数を宣言。
    global g_OLED
    global g_WIRED
    global g_BUTTON
    global g_LEDPWM
    global g_LEDHB
    #OLED(SSD1306)のi2c通信設定。
    i2c=I2C(0, sda=Pin(g_OLED_gpio["SDA"]), scl=Pin(g_OLED_gpio["SCL"]), freq=1_000_000)
    #OLED(SSD1306)とi2cを紐付け。ここでi2cでSSD1306を接続するためのスレーブアドレスはここ(i2c_id)に記載する。
    tmp=Ssd1306_i2c_JAFont(i2c,i2c_id=0x3c,x=128,y=32)
    g_OLED=tmp
    g_OLED.dispStr("INIT",fsize=4)
    g_OLED.setDefaultFsize(2)


    #ボタンを初期化しグローバル変数に保存(配列として追加)。debouncedInputを使用。
    for i in g_BUTTON_gpio_Cen:
        tmp=DebouncedInput(i, btn_callback, pin_pull=Pin.PULL_UP,pin_logic_pressed=False)
        g_BUTTON.append(tmp)
    #LEDPWM⇒リレー制御を初期化しグローバル変数に保存。諸々の都合で信号を反転している。
    for i in g_LEDPWM_gpio:
        tmp2=Pin(i,mode=Pin.OUT,value=False)
        tmp=Signal(tmp2, invert=True)
        tmp.off()
        g_LEDPWM.append(tmp)
    #LED HBを初期化しグローバル変数に保存。
    tmp=Pin(g_LEDHB_gpio[0],mode=Pin.OUT,value=False)
    g_LEDHB=tmp
    #有線判定端子を初期化しグローバル変数に保存。このピンがGNDのときは有線と判断。
    tmp=Pin(g_WIRED_gpio[0],mode=Pin.IN,pull=Pin.PULL_UP)
    g_WIRED=tmp

###############################################
#ここから有線モードの処理
###############################################

def demo_btn():
    global g_LEDHBData
    global g_BUTTONData
    #初期起動の処理
    
    #必ず顔設定を初期化する。電源投入時のみ実行される。
    multipurposeDispChange("LINEMODE")   
    for i in range(1,6):
        multipurposeDispChange("LINEMODE",clearDisp=True )
        multipurposeDispChange(str(6-i)+"secWait",y=16,clearDisp=False )
        time.sleep_ms(1000)
    RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=True)
    time.sleep_ms(350)
    RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=False)
    time.sleep_ms(150)            
    multipurposeDispChange("LINE--go")                          
    #とりあえず今はボタンアクションのみ
    while True:
        #ボタン情報の検出時に分岐
        if g_BUTTONData[0]:
            #データを一時変数にコピー
            tmp_ButtonData=g_BUTTONData[:]
            #グローバル変数を初期化し、次の入力に備える。
            g_BUTTONData=[False,0,True,0]
            #ボタンリリース時の分岐
            if tmp_ButtonData[2]==False :
                #ボタンリリースされたボタンのリレーをOFF
                RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=False,wired=True)
                #ボタンリリース時のdulationが150ms以下の時は短すぎるので追加のwait。完全に挙動不審を防げるわけでは無いが。
                if tmp_ButtonData[3]<=150:
                    time.sleep_ms(151- tmp_ButtonData[3])
                #全てのリレーをOFF。念のため…だったが同時入力回避のため必須。
                RelayOnAndDispChange(pin=g_BUTTON_gpio[0],onoff=False)
                RelayOnAndDispChange(pin=g_BUTTON_gpio[1],onoff=False)
                RelayOnAndDispChange(pin=g_BUTTON_gpio[2],onoff=False)
            #ボタン押された時の分岐
            if tmp_ButtonData[2]==True :
                #ボタン押されたボタンのリレーをON
                RelayOnAndDispChange(pin=tmp_ButtonData[1],onoff=True,wired=True)
                #ボタン押し時のdulationが350ms以下の時は短すぎるので追加のwait。完全に挙動不審を防げるわけでは無いが。
                if tmp_ButtonData[3]<=350:
                    time.sleep_ms(351- tmp_ButtonData[3])   
            #一時変数のクリア
            tmp_ButtonData=[False,0,True,0]
        #ボタン未検出なら1ms待って無限ループ
        time.sleep_ms(1)



###############################################
#ここまで有線モードの処理
###############################################

#main関数。初期化とメインプロセスの無限起動をしている。
if __name__ == "__main__":
    #電源投入直後フラグをセット
    g_onFirstTime=True
    #初期化
    init_()
    ###有線か無線かを判断するための処理
    ##2秒間待ち、その間に1秒以上有線判定端子がGND(0)のときは有線。
    ##逆に、無線のときはこの端子は開放(Hi-Z)、内部プルアップでHigh(1)になる。
    time.sleep_ms(100)
    i=0
    j=0
    #2秒間の判定時間
    while i<2000:
        i=i+1
        time.sleep_ms(1)
        #その間に有線判定端子がGND(0)のときはカウントアップ
        if not g_WIRED.value():
            j=j+1
    #メインプロセスの呼び出し無限ループ
    while True:
        if j>=1000: #有線と判定されたとき
            print ("Wired mode",j)
            #有線時の処理を呼び出し
            demo_btn()
            #電源投入直後フラグをリセット。
            g_onFirstTime=False

        else:       #無線と判定されたとき
            print ("BLE mode",j)
            #無線時の処理を呼び出し
            demo()
            #電源投入直後フラグをリセット。
            g_onFirstTime=False
