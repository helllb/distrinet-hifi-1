# distrinet-hifi
Delay-based Fidelity Monitoring of Network Emulation

## About
This project introduces Distrinet-hifi: a [Distrinet](https://distrinet-emu.github.io) plug-in to monitor fidelity of emulated experiments based on measurement of packet delays.

## Prerequisites
The scripts here use [apssh](https://github.com/parmentelat/apssh) and [asynciojobs](https://github.com/parmentelat/asynciojobs) to remotely run parallel commands on a number of nodes. First make sure you have a recent version of Python (>= 3.6), then install those on your computer:
```
pip3 install apssh asynciojobs
```
You also need to have a slice in R2Lab and your computer must be able to log onto the gatewy node. If this is not the case already, you can ask to [register](https://r2lab.inria.fr/tuto-010-registration.md) for an account.

## Installation
To set up the experiment, the R2Lab nodes must be correctly configured and running the latest stable version of Distrinet. You can use the already available images in the testbed to set up your testbed, with one master node and one or more worker nodes:
```
rhubarbe load -i u18.04-bcc_distrinet $MASTER_NODE
rhubarbe load -i u18.04-bcc_distrinet_worker $WORKER_NODE_1 $WORKER_NODE_2 ...
```

You can also manually install the testbed. Make sure to have a recent Linux Kernel (>= 4.15.0) then [install bcc](https://github.com/iovisor/bcc/blob/master/INSTALL.md) and [download and install Distrinet](https://distrinet-emu.github.io/installation.html). Then copy `hifi.py` to the mininet code directory and the rest of the files to a `/root/experiment/` directory you would have created in all the nodes of your testbed.

## Usage
First import the Distrinet-HiFi library in your Distrinet script:
```
from mininet.hifi import Monitor 
```
and wrap your experiment in the monitoring process:
```
monitor = Monitor(net)
monitor.start()
monitor.wait()
# run your experiment...
monitor.stop()
monitor.receiveData()
monitor.analyse()
```
And before running the experiment, initialise the monitoring agents on each worker of your cluster:
```
python3 agent.py 
```
