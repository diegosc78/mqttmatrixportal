# mqttmatrixportal

Led matrix simple text write from MQTT

## Disclaimer

WARNING: still alpha version. Work in progress

## Goals

Set text into led matrix panel from MQTT server (inserted there by my domotics server, openhab)

Done:

- Subscribe to a configurable topic
- Set status light in neopixel
- Optimize text size, position
- Scroll when long text
- Different text color depending on (json) message

To do:

- Manage MQTT connection errors

## References

- MatrixPortal manual: <https://cdn-learn.adafruit.com/downloads/pdf/adafruit-matrixportal-m4.pdf>
- Base example: <https://learn.adafruit.com/adafruit-matrixportal-m4/internet-connect>
- MatrixPortal API: <https://docs.circuitpython.org/projects/matrixportal/en/latest/api.htm>
- MiniMQTT API: <https://docs.circuitpython.org/projects/minimqtt/en/stable/api.html>

## Hardware

- Adafruit MatrixPortal
- HUB75 Led Matrix Panel (64x32)

## Behaviour

1. Network connection (prints MAC and IP)
2. Matrix Led initialization
3. MQTT connection initialization
4. Main loop: wait for MQTT messages and manage text scroll if necessary

On message received, update display centering message on screen.

Message format expected:

```json
{"message": "Here text", "priority":"high"}
```

Priorities are:

- high (red)
- medium (yellow)
- low (green)
- default (green)

Neopixel is also updated according to board state:

- Yellow = Connecting
- Green = Connected
- Red = Error
- Blue = Receiving

## How to flash/install

Follow this excelent tutorial: <https://learn.adafruit.com/adafruit-matrixportal-m4/prep-the-matrixportal>
