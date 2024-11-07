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
import json

# --- Init message ---
print("[MQTT Matrix Portal APP]")

# --- Get env ---
print("Getting environment parameters...")
## Wifi connection settings
wifi_ssid       = getenv("CIRCUITPY_WIFI_SSID")
wifi_password   = getenv("CIRCUITPY_WIFI_PASSWORD")
# Mqtt connection settings
mqtt_url        = getenv("MQTT_URL")
mqtt_user       = getenv("MQTT_USER")
mqtt_password   = getenv("MQTT_PASS")
mqtt_topic      = getenv("MQTT_TOPIC")

# --- Status led (neopixel) setup ---
print("Status led (neopixel) setup...")
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2) 
# Status LED colors
STATUS_CONNECTING   = 0xFFFF00  # Yellow
STATUS_CONNECTED    = 0x00FF00  # Green
STATUS_ERROR        = 0xFF0000  # Red
STATUS_RECEIVING    = 0x0000FF  # Blue

# Message priority colors
PRIORITY_COLORS = {
    "high": 0xFF0000,    # Red
    "medium": 0xFFFF00,  # Yellow
    "low": 0x00FF00,     # Green
    "default": 0x0000FF  # Default to blue
}

# Scrolling configuration
SCROLL_SPEED = 0.1  # seconds between scroll updates
scroll_position = 0
scroll_activated = False
last_scroll_update = time.monotonic()

def set_status_led(color):
    status_light.fill(color)

# --- Network connection ---
print("Network connection phase:")
esp32_cs    = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
if "SCK1" in dir(board):
    spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
else:
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
pool = adafruit_connection_manager.get_radio_socketpool(esp)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
requests = adafruit_requests.Session(pool, ssl_context)
if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print("  - ESP32 found and in idle mode")
print("  - MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))
print("  - Connecting to AP...")
set_status_led(STATUS_CONNECTING)
while not esp.is_connected:
    try:
        esp.connect_AP(wifi_ssid, wifi_password)
        set_status_led(STATUS_CONNECTED)
    except OSError as e:
        print("could not connect to AP, retrying: ", e)
        set_status_led(STATUS_ERROR)
        continue
print("  - Connected. My IP address is", esp.pretty_ip(esp.ip_address))

# --- Matrix Led Display setup ---
print("Matrix led display setup...")
matrixportal = MatrixPortal(esp=esp, external_spi=spi, debug=True)
network = matrixportal.network
try:
    network.connect()
    set_status_led(STATUS_CONNECTED)
except Exception as e:
    print(f"  - Failed to connect to WiFi: {e}")
    set_status_led(STATUS_ERROR)
    raise

# Store last received message data
last_message = None

def calculate_text_scale(text, display_width, display_height):
    """Calculate the maximum text scale that fits the display"""
    font_width, font_height = terminalio.FONT.get_bounding_box()
    
    # Calculate maximum possible scale for height
    height_scale = display_height // font_height
    
    # Calculate maximum possible scale for width
    text_width = len(text) * font_width
    width_scale = display_width // text_width if text_width > 0 else 1
    
    # Use the smaller of the two scales
    scale = min(height_scale, width_scale)
    
    # Ensure scale is at least 1
    return max(1, scale)

def update_display():
    """Update the display with the last received message"""
    global scroll_position, scroll_activated
    
    try:
        # Clear the display first
        matrixportal.set_background(0)
        
        # If no message, keep display blank
        if last_message is None:
            matrixportal.set_text("", 0)
            return
            
        message_text = last_message.get("message", "")
        priority = last_message.get("priority", "default")
        matrix_color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["default"])
        
        # Get display dimensions
        display_width = matrixportal.graphics.display.width
        display_height = matrixportal.graphics.display.height
        
        # Calculate optimal text scale
        text_scale = calculate_text_scale(message_text, display_width, display_height)
        
        # Calculate text dimensions
        fontx, fonty = terminalio.FONT.get_bounding_box()
        font_width = fontx * text_scale  # terminalio font width
        font_height = fonty * text_scale  # terminalio font height
        text_width = len(message_text) * font_width
        
        # Center text vertically
        y_pos = ((display_height - font_height) // 2) + (font_height // 2)
        
        # If text is wider than display, handle scrolling
        if text_width > display_width:
            scroll_activated = True
            # Calculate scroll offset
            x_pos = -int(scroll_position)
            # Update scroll position for next frame
            scroll_position = (scroll_position + 1) % (text_width + display_width)
        else:
            scroll_activated = False
            # Center the text horizontally for non-scrolling text
            x_pos = (display_width - text_width) // 2
            x_pos = max(0, x_pos)  # Ensure x_pos is not negative
            # Reset scroll position for centered text
            scroll_position = 0
        
        # Clear existing text
        matrixportal.remove_all_text()
        
        # Add new text with calculated position and properties
        #print(f"About to write into position ( {x_pos} , {y_pos} ) with scale {text_scale} the following text: {message_text} ...")
        matrixportal.add_text(
            text_font=terminalio.FONT,
            text_position=(x_pos, y_pos),
            text_scale=text_scale,
            text_color=matrix_color,
        )
        
        # Set the text color and text
        matrixportal.set_text_color(matrix_color, 0)
        matrixportal.set_text(message_text, 0)
            
    except Exception as e:
        print(f"Display update error: {e}")
        set_status_led(STATUS_ERROR)

def disconnect(mqtt_client, userdata, rc):
    """Called when MQTT client disconnects"""
    print("Disconnected from MQTT Broker!")
    set_status_led(STATUS_ERROR)

def message(client, topic, message):
    """Called when a message is received"""
    global last_message, scroll_position
    print(f"New message on topic {topic}: {message}")
    set_status_led(STATUS_RECEIVING)
    
    try:
        # Parse JSON message
        message_data = json.loads(message)
        # Update the last message
        last_message = message_data
        # Reset scroll position for new message
        scroll_position = 0
        # Update display
        update_display()
    except ValueError as e:  # This catches json.JSONDecodeError in CircuitPython
        print(f"Invalid JSON message: {e}")
        # If invalid JSON, treat as simple text message with default priority
        last_message = {"message": message, "priority": "default"}
        scroll_position = 0
        update_display()
    except Exception as e:
        print(f"Error processing message: {e}")
    
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
    is_ssl=False
)

def initialize_ledmatrix():
    """Initialize Led Matrix"""
    print("Initializing Led Matrix...")
    try:
        # Start with blank display
        matrixportal.add_text(
            text_font=terminalio.FONT,
            text_position=(2, int(matrixportal.graphics.display.height * 0.75) - 3),
            text_color=0x00AA00,
        )
        matrixportal.set_text("", 0)
    except Exception as e:
        print(f"  - Led matrix initialization error: {e}")
        set_status_led(STATUS_ERROR)
        raise

def initialize_mqtt():
    """Initialize MQTT connection and subscriptions"""
    print("Initializing MQTT connection...")
    try:
        if not mqtt_client.is_connected():
            set_status_led(STATUS_CONNECTING)
            mqtt_client.connect()
            set_status_led(STATUS_CONNECTED)
        mqtt_client.on_message = message
        mqtt_client.on_disconnect = disconnect
        if mqtt_client.is_connected():
            mqtt_client.subscribe(mqtt_topic, 1)
            print(f"Subscribed to {mqtt_topic}")
    except Exception as e:
        print(f"  - MQTT initialization error: {e}")
        set_status_led(STATUS_ERROR)
        raise

# --- Initial setup ---
initialize_ledmatrix()
initialize_mqtt()
update_display()  # Will show blank since last_message is None

# --- Main loop ---
print("Entering main loop...")
while True:
    try:
        if not mqtt_client.is_connected():
            print("Lost connection. Reconnecting...")
            set_status_led(STATUS_CONNECTING)
            network.connect()
            mqtt_client.reconnect()
            set_status_led(STATUS_CONNECTED)
            
        # Handle MQTT messages
        mqtt_client.loop(1.01)  # Must be greater than connection timeout (1)
        
        # Update scrolling if needed
        current_time = time.monotonic()
        if last_message is not None and scroll_activated and current_time - last_scroll_update >= SCROLL_SPEED:
            update_display()
            last_scroll_update = current_time
            
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
