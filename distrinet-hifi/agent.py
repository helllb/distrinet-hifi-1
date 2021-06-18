import socket
import pickle
import subprocess
import json
from bcc import BPF
import time
import random

HOST_IP = '10.10.20.3'
MONITOR_IP = '10.10.20.1'
PORT = 5005
MONITOR_PORT = 5005
AGENT_PORT = 5006
BUFFER = 4096
KPROBE = """
#include <net/sch_generic.h>
#include <bcc/proto.h>
#include <uapi/linux/ptrace.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/icmp.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/in.h>


int kprobe__htb_enqueue(struct pt_regs *ctx, struct sk_buff *skb, struct Qdisc *sch, struct sk_buff **to_free)
{
   void *data = (void *)(long)skb->data;									 
   struct iphdr *iph = (struct iphdr *)(skb->head + skb->network_header);

   // if (iph->protocol == IPPROTO_ICMP) {
	  unsigned short int id = iph->id;
	  unsigned short int fo = iph->frag_off;
	  id = (id << 8) | (id >> 8);
	  fo = (fo << 8) | (fo >> 8);
	  unsigned int xid = (id << 16) | fo;

	  // unsigned long long ts = bpf_ktime_get_ns();

	  // unsigned int len = skb->len;
	  unsigned int blen = sch->qstats.backlog;
	  int dev = skb->dev->ifindex;

	  bpf_trace_printk("[enq] %d %u %u\\n", dev, xid, blen);
   // }
		 
   return 0;
}
												
int kretprobe__htb_dequeue(struct pt_regs *ctx, struct Qdisc *sch)  
{   
   struct sk_buff *skb = (struct sk_buff *)PT_REGS_RC(ctx);
   
   if (skb) {
	  unsigned int len = skb->len;
	  int dev = skb->dev->ifindex;
	  // unsigned long long ts = bpf_ktime_get_ns();

	  bpf_trace_printk("[deq] %d %u\\n", dev, len);
   }
   
   return 0;
}
"""





def run(cmd):
	res = subprocess.run(cmd, stdout=subprocess.PIPE)
	ret = res.stdout.decode()[:-1]
	return ret


def runBG(cmd, output):
	f = open(output, 'w')
	p = subprocess.Popen(cmd, stdout=f)
	return p


class Agent:
	# TODO: Remove self.IP (replace with HOST_IP)
	def __init__(self, info):
		self.IP = HOST_IP
		self.nodes = []

		for node in info['nodes']:
			name = node['name']
			newNode = Node(name)
			self.addNode(newNode)

			for intf in node['interfaces']:
				name = intf['name']
				bw = intf['bw']
				newIntf = Intf(name, bw)
				newNode.addIntf(newIntf)
		

	def addNode(self, node):
		self.nodes.append(node)
		node.setAgent(self)

		return

	def prepare(self):
		# Merge into self.start()

		print("** Preparing host %s" % self.IP)
		cmd = ["mkdir", "-p", "/var/run/netns"]
		run(cmd)
		print("** Agent %s prepared" % self.IP)

		return

	
	def start(self):
		self.prepare()

		print("** Launching probe on host %s" % self.IP)

		self.kprobe = BPF(text = KPROBE)

		cmd = ["pkill", "cat"]
		run(cmd)

		output = "/root/experiment/bpf_%s.out" % self.IP
		cmd = ["cat", "/sys/kernel/debug/tracing/trace_pipe"]
		runBG(cmd, output)
		
		print("** Probe launched on host %s" % self.IP)

		for node in self.nodes:
			for intf in node.intfs:
				intf.plugeBPF()

		return

	def ready(self):
		print("* Notifying monitor...")
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		while True:
			try:
				sock.connect((MONITOR_IP, MONITOR_PORT))
				break
			except:
				t = .5 + random.expovariate(1)
				print("* Monitor busy. Retrying in %.2f seconds..." % t)
				time.sleep(t)
		sock.close()

		return

	def wait(self):
		print("* Waiting for experiment...")
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.bind((HOST_IP, AGENT_PORT))

		sock.listen()

		conn, addr = sock.accept()
		conn.close()

		sock.close()
		print("* Experiment finished")

		return
		
	def stop(self):
		print("** Stopping Agent %s" % self.IP)

		cmd = ["pkill", "cat"]
		run(cmd)

		cmd = ["rm", "-rf", "/var/run/netns"]
		run(cmd)

		print("** Agent %s stopped" % self.IP)

		return



class Node:
	def __init__(self, name):
		self.name = name
		self.intfs = []
		self.pid = None

	def setAgent(self, agent):
		self.agent = agent

	def addIntf(self, intf):
		self.intfs.append(intf)
		intf.setNode(self)

	def getPID(self):
		if self.pid is None:
			cmd = ["sh", "/root/experiment/netns.sh", self.name]
			self.pid = int(run(cmd))

		return self.pid



class Intf:
	def __init__(self, name, bw=100):
		self.name = name
		self.ifindex = None
		self.bw = bw

	def setNode(self, node):
		self.node = node

	def getIfindex(self):
		if self.ifindex is None:
			pid = self.node.getPID()
			cmd = ["ip", "netns", "exec", str(pid), "python3", "-c", "import socket; print(socket.if_nametoindex('%s'))" % self.name]
			self.ifindex = int(run(cmd))

		return self.ifindex

	def plugeBPF(self):
		print("*** Plugging eBPF program into interface %s" % self.name)

		pid = self.node.getPID()
		ifindex = self.getIfindex()
		cmd = ["sh", "/root/experiment/compile.sh", str(pid), self.name, "%iMbit" % self.bw]
		ret = run(cmd)
		print(cmd)
		print(ret)

		print("*** eBPF program plugged into interface %s" % self.name)
		print("*** Interface %s has index %i" % (self.name, self.ifindex))


def receiveInfo():
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.bind((HOST_IP, AGENT_PORT))

	print("* Waiting for Collector/Analyser at %s:%s..." % (HOST_IP, AGENT_PORT))
	sock.listen(1)

	conn, addr = sock.accept()
	print("* Connected to Collector/Analyser at %s:%s" % addr)

	print("* Receiving control information...")
	raw = bytes()
	while True:
		rec = conn.recv(BUFFER)
		if not rec:
			break
		else:
			raw += rec
	print("* Information received")
	print(raw)
	info = pickle.loads(raw)

	sock.close()

	return info



# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# ------------------------------_Analysis_-----------------------------
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------

import re
import json

length = len

PATTERN_IN   = re.compile(r"^.*\s(?P<ts>[0-9]+\.[0-9]+):.*\s\[in\]\s(?P<dev>[0-9]+)\s(?P<xid>[0-9]+)\s*$")
PATTERN_OUT  = re.compile(r"^.*\s(?P<ts>[0-9]+\.[0-9]+):.*\s\[out\]\s(?P<dev>[0-9]+)\s(?P<xid>[0-9]+)\s(?P<len>[0-9]+)\s*$")
PATTERN_ENQ = re.compile(r"^.*\s\[enq\]\s(?P<dev>[0-9]+)\s(?P<xid>[0-9]+)\s(?P<blen>[0-9]+)\s*$")
PATTERN_DEQ  = re.compile(r"^.*\s(?P<ts>[0-9]+\.[0-9]+):.*\s\[deq\]\s(?P<dev>[0-9]+)\s(?P<len>[0-9]+)\s*$")

class DataBase:
	def __init__(self, agent):
		self.filename = "bpf_%s.out" % agent.IP
		self.agent = agent

		self.ifindexes = {}
		for node in agent.nodes:
			for intf in node.intfs:
				name = intf.name
				ifindex = intf.getIfindex()
				self.ifindexes[ifindex] = name

		self.ins = {ifindex: {} for ifindex in self.ifindexes}  
		self.outs = {ifindex: {} for ifindex in self.ifindexes}

		self.lastt = {ifindex: None for ifindex in self.ifindexes}
		self.lastl = {ifindex: None for ifindex in self.ifindexes}

	def parse_line(self, line):
		if '[in]' in line:
			m = PATTERN_IN.match(line)
			if m is not None:
				dev, xid, ts = int(m.group('dev')), int(m.group('xid')), int(1e6*float(m.group('ts')))
				if dev in self.ifindexes:
					arr = self.ins[dev].get(xid)
					if arr is not None:
						arr.append((ts))
					else:
						self.ins[dev][xid] = [(ts)]
				return
		
		elif '[enq]' in line:
			m = PATTERN_ENQ.match(line)
			if m is not None:
				dev, xid, blen = int(m.group('dev')), int(m.group('xid')), int(m.group('blen'))
				if dev in self.ifindexes:
					arr = self.outs[dev].get(xid)
					if arr is not None:
						arr.append(blen)
					else:
						self.outs[dev][xid] = [blen]
				return

		elif '[out]' in line:
			m = PATTERN_OUT.match(line)
			if m is not None:
				dev, xid, ts, len = int(m.group('dev')), int(m.group('xid')), int(1e6*float(m.group('ts'))), int(m.group('len'))
				if dev in self.ifindexes:
					arr = self.outs[dev].get(xid)
					if arr is not None:
						blen = self.outs[dev][xid][-1]
						tau = 0
						plen = 0
						if self.lastl[dev] is not None:
							tau = ts - self.lastt[dev] # us
							plen = self.lastl[dev]
						self.outs[dev][xid][-1] = (ts, len, blen, plen, tau)
				return

		elif '[deq]' in line:
			m = PATTERN_DEQ.match(line)
			if m is not None:
				dev, ts, len = int(m.group('dev')), int(1e6*float(m.group('ts'))), int(m.group('len'))
				if dev in self.ifindexes:
					self.lastt[dev] = ts
					self.lastl[dev] = len
				return

	def parse(self):
		with open(self.filename, 'r') as f:
			lines = f.readlines()
			for line in lines:
				self.parse_line(line)

	def __str__(self):
		data = {}
		for ifindex in self.ifindexes:
			name = self.ifindexes[ifindex]
			data[name] = {'packets_in': self.ins[ifindex], 'packets_out': self.outs[ifindex]}
		return json.dumps(data)


	def sendData(self):
		data = {}
		for ifindex in self.ifindexes:
			name = self.ifindexes[ifindex]
			data[name] = {'packets_in': self.ins[ifindex], 'packets_out': self.outs[ifindex]}
		raw = pickle.dumps(data)

		print("* Sending data to monitor...")
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		while True:
			try:
				sock.connect((MONITOR_IP, MONITOR_PORT))
				break
			except:
				t = .5 + random.expovariate(1)
				print("* Monitor busy. Retrying in %.2f seconds..." % t)
				time.sleep(t)

		N = len(raw)
		i = 0
		while i < N:
			if i+BUFFER < N:
				sent = raw[i: i+BUFFER]
			else:
				sent = raw[i:]
			i += BUFFER
			sock.send(sent)
		print("* Data sent")

		sock.close()

		return




if __name__ == "__main__":
	# sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	# sock.bind((HOST_IP, PORT))

	# print("* Waiting for Collector/Analyser in %s:%s..." % (HOST_IP, PORT))
	# sock.listen(1)

	# conn, addr = sock.accept()
	# print("* Connected to Collector/Analyser at %s:%s" % addr)

	# print("* Receiving data...")
	# raw = conn.recv(BUFFER)

	# print("* Data received. Analysing...")
	# print(raw)
	# data = pickle.loads(raw)
	# # print(json.dumps(data, indent=4, sort_keys=True))

	# while True:
	info = receiveInfo()

	agent = Agent(info)
	agent.prepare()
	agent.start()

	agent.ready()

	agent.wait()
	agent.stop()

	database = DataBase(agent)
	database.parse()
	database.sendData()

	
