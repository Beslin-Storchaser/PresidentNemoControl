# PresidentNemoControl (ネモ社長制御)

## 概要
ゲーム Library of Ruina(作：ProjectMoon)に登場する、杖事務所 ネモ社長のコスプレをした際の、画面側(セントラル側)、リモコン側(ペリフェラル側)のそれぞれの制御プログラムです。  
本プログラムは、拙作の同人誌及びコスプレに対応したものとなります。  
拙作の同人誌は以下をご参照ください（有料となります）  
https://www.melonbooks.co.jp/detail/detail.php?product_id=3201278

プログラム言語（Program Language)：MicroPython  
対象機種(Target)：Raspberry Pi Pico W、 Raspberry Pi Pico 2W（未検証）  
（無線(Bluetooth)機能必須のため、W無しのものでは動作しません)  
各々約12個のGPIOを使用します。  

## 使用方法
### *前準備
UUIDを3つ生成し、peripheral/main.pyとcentral/main_oled.py、central/main_7seg.pyのUUIDの行を書き換えてください。  
UUIDの生成方法はここを参照ください：https://monomonotech.jp/kurage/webbluetooth/uuid.html
```
ファイル：　peripheral/main.py
#83行目付近
_UART_UUID = bluetooth.UUID("***ここに1つ目のUUIDを入れる***")
_UART_TX = (
    bluetooth.UUID("***ここに2つ目のUUIDを入れる***"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_UART_RX = (
    bluetooth.UUID("***ここに3つ目のUUIDを入れる***"),
    _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)
```
```
ファイル：　central/main_oled.py、central/main_7seg.py
#57行目付近
_UART_SERVICE_UUID = bluetooth.UUID("***ここに1つ目のUUIDを入れる***")
_UART_TX_CHAR_UUID = bluetooth.UUID("***ここに2つ目のUUIDを入れる***")
_UART_RX_CHAR_UUID = bluetooth.UUID("***ここに3つ目のUUIDを入れる***")
```
順番が間違っていたりするとBLE接続がうまくいかないので注意してください。  

### *次のステップ
**リモコン側**
peripheral/main.pyをRaspberry Pi Pico Wのルートフォルダに保存してください。

**画面側**
1. central/ssd1306_i2c_JAFont.pyをRaspberry Pi Pico Wのルートフォルダに保存してください。
2. 以下のどちらかを実行してください。   
   **OLED使用の場合**：central/main_oled.pyをmain.pyにリネームしてRaspberry Pi Pico Wのルートフォルダに保存してください。  
   **7セグ使用の場合**：central/main_7seg.pyをmain.pyにリネームしてRaspberry Pi Pico Wのルートフォルダに保存してください。  

## 必要なライブラリ（別途、Raspberry Pi Pico Wに導入（コピー）が必要）
**リモコン側**
- ble_advertising
Bluetooth Low Energyの中核。  
https://github.com/micropython/micropython/tree/master/examples/bluetooth  
上記URLから ble_advertising.py を入手してRaspberry Pi Pico Wに導入してください。  
もしくは、上記URLの ble_advertising.py を開いて、プログラムをすべてコピーしてエディタ（Thonny等）にてRaspberry Pi Pico Wのルートフォルダに保存してください。  

- debounced_input
ボタン押し下げ時のデバウンス（チャタリング防止）用。  
https://github.com/jmcclin2/updebouncein  
上記URLから debounced_input.pyを入手してください。導入方法は上記と同様です。  

**画面側**
- ble_advertising
Bluetooth Low Energyの中核。  
https://github.com/micropython/micropython/tree/master/examples/bluetooth  
上記URLから ble_advertising.py を入手してRaspberry Pi Pico Wに導入してください。  
もしくは、上記URLの ble_advertising.py を開いて、プログラムをすべてコピーしてエディタ（Thonny等）にてRaspberry Pi Pico Wのルートフォルダに保存してください。  

- debounced_input
ボタン押し下げ時のデバウンス（チャタリング防止）用。  
https://github.com/jmcclin2/updebouncein  
上記URLから debounced_input.pyを入手してください。導入方法は上記と同様です。  

- max7219_8digit.py
MAX7219 ICを経由して7セグメントLED8個を点灯する場合に必要。  
https://github.com/pdwerryhouse/max7219_8digit  
上記URLから max7219_8digit.pyを入手してください。導入方法は上記と同様です。  

- ssd1306_i2c_JAFont
拙作、SSD1306を使用するための簡易ラッパー関数群です。  
同梱のssd1306_i2c_JAFont.pyを使用してください。導入方法は使用方法に記載しています。  

- ssd1306
ssd1306を使用するOLEDディスプレイモジュールの動作プログラムです。  
こちらはエディタのパッケージ管理機能などでライブラリをインストールして使用してください。  
パッケージ名：micropython-ssd1306  

- Misakifont
8x8サイズに収まる日本語フォントです。  
https://github.com/Tamakichi/pico_MicroPython_misakifont  
上記URLからリスト右上の緑のボタン「<>Code」をクリック、「Download ZIP」で入手してください。  
上記ZIPを解凍して、misakifontディレクトリをそのままRaspberry Pi Pico Wに保存してください。  

上記2つ(SSD1306,Misakifont)のライブラリに関する参考情報：  
https://wisteriahill.sakura.ne.jp/CMS/WordPress/2023/04/30/pi-pico-setup-micropython-memo-2/  

これら以外のライブラリはパッケージ管理機能を使用してインストールできるはずですので、不足する場合は一般的な導入手順に従ってください。  

ディレクトリツリーは以下の通りになります。  
**リモコン側(全てルートフォルダ)**
```
/
|   ble_advertising.py
|   debounced_input.py
|   main.py
```

**画面側(ルートフォルダより)**
```
/
│  ble_advertising.py
│  debounced_input.py
│  main.py
│  max7219_8digit.py
│  ssd1306_i2c_JAFont.py
│
├─lib
│  │  ssd1306.py
│  │
│  └─ssd1306-0.1.0.dist-info
│          METADATA
│          RECORD
│
└─misakifont
        misakifont.py
        misakifontdata.py
        tma_jp_utl.py
        __init__.py
```

## プログラムの改変について
個人的使用については特に制限はありません。  
基本的に改変については特に制限しておりません。  
勝手にこのプログラムを作ったと名乗らない限りは問題ありません。  
有償再販売は禁じます。（これは商用利用を制限するものではありません）  
それ以外はApache-2.0 Licenseに準拠します。  
改良版のリクエスト等は受け付けますが、必ず対応することを約束はいたしかねます。  
