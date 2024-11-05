from os import getenv
import board
import busio
import terminalio
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import time
import adafruit_connection_manager
import adafruit_requests
import neopixel
from digitalio import DigitalInOut

# --- Get env ---
wifi_ssid = getenv("CIRCUITPY_WIFI_SSID")
wifi_password = getenv("CIRCUITPY_WIFI_PASSWORD")
mqtt_url = getenv("MQTT_URL")
mqtt_user = getenv("MQTT_USER")
mqtt_password = getenv("MQTT_PASS")
mqtt_topic = getenv("MQTT_TOPIC")

# --- Network connection ---
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
if "SCK1" in dir(board):
    spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
else:
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
status_light = neopixel.NeoPixel(
    board.NEOPIXEL, 1, brightness=0.2
) 
pool = adafruit_connection_manager.get_radio_socketpool(esp)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
requests = adafruit_requests.Session(pool, ssl_context)
if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print("ESP32 found and in idle mode")
print("MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))
print("Connecting to AP...")
while not esp.is_connected:
    try:
        esp.connect_AP(wifi_ssid, wifi_password)
    except OSError as e:
        print("could not connect to AP, retrying: ", e)
        continue
print("My IP address is", esp.pretty_ip(esp.ip_address))

# --- Display setup ---
matrixportal = MatrixPortal(esp=esp, external_spi=spi, debug=True)
network = matrixportal.network

# Status LED colors
STATUS_CONNECTING = 0xFFFF00  # Yellow
STATUS_CONNECTED = 0x00FF00   # Green
STATUS_ERROR = 0xFF0000      # Red
STATUS_RECEIVING = 0x0000FF  # Blue

def set_status_led(color):
    status_light.fill(color)
    #matrixportal.status_neopixel.fill(color)

# Try to connect to WiFi
set_status_led(STATUS_CONNECTING)
try:
    network.connect()
    set_status_led(STATUS_CONNECTED)
except Exception as e:
    print(f"Failed to connect to WiFi: {e}")
    set_status_led(STATUS_ERROR)
    raise

# Store last received message
last_message = "Waiting..."

def update_display():
    """Update the display with the last received message"""
    try:
        # Clear the display first
        matrixportal.set_background(0)
        # Calculate text scale based on message length
        text_scale = 1 if len(last_message) > 8 else 2
        # Update text with new scale
        matrixportal.set_text(last_message, 0)
    except Exception as e:
        print(f"Display update error: {e}")
        set_status_led(STATUS_ERROR)

def disconnect(mqtt_client, userdata, rc):
    """Called when MQTT client disconnects"""
    print("Disconnected from MQTT Broker!")
    set_status_led(STATUS_ERROR)

def message(client, topic, message):
    """Called when a message is received"""
    global last_message
    print(f"New message on topic {topic}: {message}")
    set_status_led(STATUS_RECEIVING)
    
    # Update the last message and display
    last_message = message
    update_display()
    
    # Return to connected status
    time.sleep(0.2)  # Brief flash of blue to show receipt
    set_status_led(STATUS_CONNECTED)

# --- Set up a MiniMQTT Client ---
mqtt_client = MQTT.MQTT(
    broker=mqtt_url,
    username=mqtt_user,
    password=mqtt_password,
    client_id="matrixportal",
    socket_pool=pool,
    ssl_context=ssl_context,    
    is_ssl = False
)

# --- Show initial text ---
matrixportal.add_text(
    text_font=terminalio.FONT,
    text_position=(2, int(matrixportal.graphics.display.height * 0.75) - 3),
    text_color=0x00AA00,
)

def initialize_mqtt():
    """Initialize MQTT connection and subscriptions"""
    try:
        if not mqtt_client.is_connected():
            set_status_led(STATUS_CONNECTING)
            mqtt_client.connect()
            set_status_led(STATUS_CONNECTED)
            
        mqtt_client.on_message = message
        mqtt_client.on_disconnect = disconnect
        mqtt_client.subscribe(mqtt_topic, 1)
        print(f"Subscribed to {mqtt_topic}")
    except Exception as e:
        print(f"MQTT initialization error: {e}")
        set_status_led(STATUS_ERROR)
        raise

# Initial setup
initialize_mqtt()
update_display()

# Main loop
while True:
    try:
        if not mqtt_client.is_connected():
            set_status_led(STATUS_CONNECTING)
            network.connect()
            mqtt_client.reconnect()
            set_status_led(STATUS_CONNECTED)
        mqtt_client.loop(2)
    except (MQTT.MMQTTException, RuntimeError) as e:
        print(f"Connection error: {e}")
        set_status_led(STATUS_ERROR)
        time.sleep(5)  # Wait before retry
        continue
    except Exception as e:
        print(f"Unexpected error: {e}")
        set_status_led(STATUS_ERROR)
        time.sleep(5)  # Wait before retry
        continue
