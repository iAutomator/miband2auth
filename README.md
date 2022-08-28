# miband2auth: a utility for connection to Mi Band 2

You may want to play with Mi Band 2 using a Linux machine. You start `bluetoothctl` or any other tool capable of BLE comminication, then connect to the device and start getting familiar with proposed GATT services. But 20sec later the device gets disconnected unexpectedly. `miband2auth` solves the problem.

Mi Band 2 requires a special auth procedure for permanent connection establishment. Without it the device does not execute sent commands and connection gets timed out. miband2auth executes the needed procedure making the device available for interaction.

# Operation

The utility can be used either as a standalone script or as a library.

## Standalone script

The script authentificates all observed devices on connection. So to use it you need to run it before connecting to the device.

## Library

It can be used as a library by any other application intending to control Mi Band 2.

# Acknowledgments

The auth procedure is implemented based on findings of provided at the following page: https://medium.com/machine-learning-world/how-i-hacked-xiaomi-miband-2-to-control-it-from-linux-a5bd2f36d3ad