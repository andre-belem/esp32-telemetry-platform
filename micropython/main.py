# --- LIBRARIES --- 
import network 
import machine 
import time 
from machine import RTC, ADC, Pin 
from umqtt.simple import MQTTClient 
import dht 
import ujson 
import ntptime 
import usocket # <--- Trocado urequests por usocket para controle absoluto de RAM
import gc 

# Importa o dicionário protegido do arquivo local da Flash
from config import settings

# --- CONFIGURAÇÕES DA REDE CARREGADAS DA FLASH --- 
DEVICE_ID = settings["DEVICE_ID"]
DEVICE_NAME = settings["DEVICE_NAME"] 
WIFI_SSID = settings["WIFI_SSID"] 
WIFI_PASSWORD = settings["WIFI_PASSWORD"] 
MQTT_BROKER = settings["MQTT_BROKER"] 
MQTT_PORT = settings["MQTT_PORT"] 
MQTT_USER = settings["MQTT_USER"] 
MQTT_PASSWORD = settings["MQTT_PASSWORD"] 
MQTT_TOPIC_SUB = settings["MQTT_TOPIC_SUB"] 
MQTT_TOPIC_PUB = settings["MQTT_TOPIC_PUB"]

# --- CONFIGURAÇÕES DE PINOUT --- 
LED_BOARD = machine.Pin(2, machine.Pin.OUT) 
LED_WIFI = machine.Pin(23, machine.Pin.OUT) 
LED_MQTT = machine.Pin(22, machine.Pin.OUT) 
LED_SEND = machine.Pin(19, machine.Pin.OUT) 
LED_RECEIVE = machine.Pin(18, machine.Pin.OUT)
LED_BATT = machine.Pin(15, machine.Pin.OUT)

PINO_DHT = machine.Pin(4, machine.Pin.IN, machine.Pin.PULL_UP) 

LDR = ADC(Pin(34)) 
LDR.atten(ADC.ATTN_11DB) 
LDR.width(ADC.WIDTH_12BIT)

V_BAT = ADC(Pin(35)) 
V_BAT.atten(ADC.ATTN_11DB) 
V_BAT.width(ADC.WIDTH_12BIT)

V_CHUVA = ADC(Pin(39)) 
V_CHUVA.atten(V_CHUVA.ATTN_11DB) 
V_CHUVA.width(V_CHUVA.WIDTH_12BIT)
D_CHUVA = Pin(36, Pin.IN) 

V_SOLAR = ADC(Pin(33)) 
V_SOLAR.atten(V_CHUVA.ATTN_11DB) 
V_SOLAR.width(V_CHUVA.WIDTH_12BIT)

V_TEMP_BATT = ADC(Pin(32))

# --- DEFINE THE DATA VARIABLES --- 
timestamp = "0000-00-00 00:00:00" 
temperature = 00.0 
humidity = 00.0 
light_level = 0 
local_ip = "0.0.0.0" 
public_ip = "0.0.0.0" 
rssi = 0 
v_bat = 101 
firmware = "VERSION2" 
up_time = 0
R1 = 10000.0  # 10k Ohms
R2 = 3300.0   # 3k3 Ohms
v_chuva = 0.0

# --- INICIALIZAÇÃO DOS SENSORES --- 
DHT_SENSOR = dht.DHT22(PINO_DHT) 
rtc = RTC()

# --- INICIALIZAÇÃO DOS LEDS ---
LED_BOARD.value(1)
LED_WIFI.value(0) 
LED_MQTT.value(0) 
LED_SEND.value(0) 
LED_RECEIVE.value(0)
LED_BATT.value(0)

# 1. Crie essa variável global no início do seu script (fora do loop)
tensao_filtrada = None

def filtrar_onda_buck(novo_valor):
    global tensao_filtrada
    if tensao_filtrada is None:
        tensao_filtrada = novo_valor
        return tensao_filtrada
    
    # Fator de suavização (Alfa). Quanto menor (ex: 0.05), mais reta fica a linha
    alfa = 0.08 
    tensao_filtrada = (alfa * novo_valor) + ((1 - alfa) * tensao_filtrada)
    return tensao_filtrada

# --- FUNÇÃO PARA CONEXÃO DO WIFI --- 
def do_connect(ssid, password): 
    global local_ip 
    global rssi 
    wlan = network.WLAN(network.STA_IF) 
    wlan.active(True) 
    if not wlan.isconnected(): 
        print('connecting to network...') 
        wlan.connect(ssid, password) 
        while not wlan.isconnected(): 
            machine.idle() 
    print('network config:', wlan.ifconfig()) 
    local_ip = wlan.ifconfig()[0] 
    rssi = wlan.status('rssi') 
    LED_WIFI.value(1) 

# --- FUNÇÃO COM SOCKET PURO PARA PEGAR IP PÚBLICO (ULTRA LEVE) --- 
def obter_ip_publico():
    global public_ip
    gc.collect()
    
    try:
        print("Buscando IP público via Socket TCP...")
        # Resolve o endereço IP do servidor api.ipify.org
        ai = usocket.getaddrinfo("api.ipify.org", 80)
        addr = ai[0][-1]
        
        # Cria o socket TCP
        s = usocket.socket()
        s.settimeout(5.0)
        s.connect(addr)
        
        # Envia a requisição HTTP bruta (Consome quase zero de RAM)
        s.send(b"GET / HTTP/1.1\r\nHost: api.ipify.org\r\nConnection: close\r\n\r\n")
        
        # Lê a resposta em blocos
        resposta = b""
        while True:
            chunk = s.recv(64) # Lê apenas 64 bytes por vez
            if not chunk:
                break
            resposta += chunk
            
        s.close()
        
        # Separa os cabeçalhos HTTP do corpo do texto (onde fica o IP)
        resposta_str = resposta.decode('utf-8')
        if "\r\n\r\n" in resposta_str:
            public_ip = resposta_str.split("\r\n\r\n")[1].strip()
            print(f"IP Público detectado com sucesso: {public_ip}")
        else:
            public_ip = "0.0.0.0"
            
    except Exception as e:
        print("Erro ao obter IP público via socket:", e)
        public_ip = "0.0.0.0"
    
    gc.collect()

# --- FUNÇÃO PARA RECEBER MENSAGENS MQTT --- 
def callback_mensagem(topico, mensagem): 
    print(f"MSG RECEIVED: {topico.decode()}: {mensagem.decode()}") 
    LED_RECEIVE.toggle() 

# --- FUNÇÃO PARA ATUALIZAR RTC --- 
def atualizar_rtc_com_fuso(fuso_horario=-3): 
    try: 
        print("Sincronizando com o servidor NTP...")
        ntptime.settime() 
        segundos_locais = time.time() + (fuso_horario * 3600) 
        data_local = time.localtime(segundos_locais) 
        rtc.datetime((data_local[0], data_local[1], data_local[2], data_local[6], data_local[3], data_local[4], data_local[5], 0)) 
        print("Relógio local configurado!") 
    except Exception as e: 
        print("Falha na configuração do relógio:", e) 

# --- FUNÇÃO PARA LER TENSÃO DA BATERIA --- 
def ler_tensao_bateria():
    soma_amostras = 0
    num_amostras = 16
    
    constante_calibracao = 0.009
    
    # Média de 16 leituras para eliminar ruídos elétricos
    for _ in range(num_amostras):
        soma_amostras += V_BAT.read()
        time.sleep_ms(5)
        
    valor_adc = soma_amostras / num_amostras
    
    # Converte o valor do ADC para a tensão medida no pino 35
    #tensao_pino = (valor_adc * 3.3) / 4095.0
    
    # Calcula a tensão real da bateria 5S baseada no seu divisor de tensão
    #tensao_bateria = tensao_pino * ((R1 + R2) / R2)
    tensao_bateria = valor_adc * constante_calibracao
    
    tensao_perfeita = filtrar_onda_buck(tensao_bateria)

    if tensao_bateria is None:
        tensao = 0.0
        
    if tensao_bateria < 18:
        LED_BATT.value(1)
    else:
        LED_BATT.value(0)
    
    return tensao_bateria


# --- FUNÇÃO PARA LER TENSÃO DA BATERIA --- 
def ler_tensao_chuva():
    soma_amostras = 0
    num_amostras = 16
    
    # Média de 16 leituras para eliminar ruídos elétricos
    for _ in range(num_amostras):
        soma_amostras += V_CHUVA.read()
        time.sleep_ms(5)
        
    valor_adc = soma_amostras / num_amostras
    
    # Converte o valor do ADC para a tensão medida no pino 35
    tensao_pino = (valor_adc * 3.3) / 4095.0
    
    return tensao_pino


# --- MAIN --- 
print("Iniciando em 5 segundos... Pressione Ctrl+C para cancelar.") 
time.sleep(5) 

# Conecta ao WiFi primeiro
do_connect(WIFI_SSID, WIFI_PASSWORD) 

# Busca o IP público e ajusta o relógio usando a internet
obter_ip_publico() 
atualizar_rtc_com_fuso(-3) 

print("Data e Hora local:", time.localtime()) 

# --- CONFIGURA O MQTT --- 
client = MQTTClient(DEVICE_ID, MQTT_BROKER, port=MQTT_PORT, user=MQTT_USER, password=MQTT_PASSWORD) 
client.set_callback(callback_mensagem) 

try: 
    print("Conectando ao broker MQTT...") 
    client.connect() 
    print("Conectado ao MQTT!") 
    client.subscribe(MQTT_TOPIC_SUB) 
    LED_MQTT.value(1) 
    
    client.publish(MQTT_TOPIC_PUB, f"Cliente Conectado {DEVICE_ID}") 

    while True: 
        try: 
            DHT_SENSOR.measure() 
            light_level = LDR.read() 
            
            temperature = "{:2.1f}".format(DHT_SENSOR.temperature()) 
            humidity = "{:2.1f}".format(DHT_SENSOR.humidity()) 
            
            agora = rtc.datetime() 
            timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(agora[0], agora[1], agora[2], agora[4], agora[5], agora[6]) 

            # Atualiza a força do sinal WiFi
            try:
                wlan = network.WLAN(network.STA_IF)
                rssi = wlan.status('rssi')
            except:
                pass
            
            # Lê tensão da bateria
            v_bat = round(ler_tensao_bateria(), 2)


            # Lê tensão da chuva
            v_chuva = round(ler_tensao_chuva(), 1)
            
            # --- ORGANIZE DATA INTO A PYTHON DICTIONARY --- 
            sensor_data = { 
                "Device_id": DEVICE_ID,
                "Device_name": DEVICE_NAME,
                "Time": timestamp, 
                "Temperature_C": temperature, 
                "Humidity_Percent": humidity, 
                "Light_ADC": light_level, 
                "Local_Ip": local_ip, 
                "public_ip": public_ip, 
                "RSSI": rssi, 
                "Battery": v_bat, 
                "Firmware": firmware, 
                "Up_Time": up_time,
                "V_Chuva": v_chuva
            } 

            json_message = ujson.dumps(sensor_data) 
            client.publish(MQTT_TOPIC_PUB, json_message) 
            LED_SEND.toggle() 
            print("Dados enviados para o BROKER.") 
            
        except OSError as e: 
            print("Falha ao ler o sensor DHT22 ou enviar dados") 

        client.check_msg() 
        LED_BOARD.value(1) 
        time.sleep(0.5) 
        LED_BOARD.value(0) 
        time.sleep(0.5) 
        up_time = up_time + 1 
        # 1. Total bytes currently used by your program
        used = gc.mem_alloc()

        # 2. Total bytes still free for new data
        free = gc.mem_free()

        # 3. Total heap size available to MicroPython
        total = used + free

        print(f"Used: {used} bytes")
        print(f"Free: {free} bytes")
        print(f"Total Heap: {total} bytes")
        gc.collect() 

except OSError as e: 
    print("Falha ao conectar ao MQTT:", e)
