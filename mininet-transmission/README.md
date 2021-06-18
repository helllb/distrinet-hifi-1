# Transmission delay in Mininet

## About
The transmission delay, defined as the time duration for the transmission hardware (NIC, switch port, router interface, etc.) to write a frame into the transmission medium, is not properly emulated in Mininet.
This small experiment here demonstrates this.

## Prerequisites
[Pingparsing](https://pypi.org/project/pingparsing/) is used to parse Ping output.
```
pip3 install pingparsing
```

## Usage
If you already have access to an R2Lab slice, simply run the nepi-ng script from your laptop:
```
python3 transmission.py --slice=$USERNAME
```

Otherwise
