# mqttmatrixportal

Led matrix simple text write from MQTT

## Disclaimer

WARNING: still alpha version. Work in progress

## Goals

Set text into led matrix panel from MQTT server (inserted there by my domotics server, openhab)

Done:

- Subscribe to a configurable topic
- Set status light in neopixel

Work in progress:

- Manage reconnections

To do:

- Optimize text size, position
- Different text color depending on (json) message
- No default message ("waiting...")

## References

- MatrixPortal manual: <https://cdn-learn.adafruit.com/downloads/pdf/adafruit-matrixportal-m4.pdf>
- Base example: <https://learn.adafruit.com/adafruit-matrixportal-m4/internet-connect>
- MatrixPortal API: <https://docs.circuitpython.org/projects/matrixportal/en/latest/api.htm>
- MiniMQTT API: <https://docs.circuitpython.org/projects/minimqtt/en/stable/api.html>
