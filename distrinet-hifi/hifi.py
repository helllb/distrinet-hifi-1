from bcc import BPF
from mininet.cli import CLI
from mininet.log import info
from mininet.topo import Topo
import json
import socket
import pickle
import time
import numpy as np

PORT = 5005
MONITOR_PORT = 5005
AGENT_PORT = 5006
BUFFER = 4096
MONITOR_IP = '10.10.20.1'

class Monitor:
	def __init__(self, net, unmonitor=['admin']):
		self.info = []
		hostIPs = []
		self.links = []
		self.unmonitor=unmonitor

		for lxc in net.hosts + net.switches:
			# hostSsh = lxc.targetSsh
			hostIP = lxc.target

			# if hostIP not in hostIPs:
			# 	info[hostIP] = []
			try:
				i = hostIPs.index(hostIP)
				host = self.info[i]
			except ValueError:
				hostIPs.append(hostIP)
				host = {'IP': hostIP, 'nodes': []}
				self.info.append(host)

			# 	host = Host(hostSsh, hostIP)
			# 	self.hosts.append(host)

			# nodeIP = lxc.admin_ip
			# nodeSsh = lxc.ssh
			nodeName = lxc.name

			node = {'name': nodeName, 'interfaces': []}
			host['nodes'].append(node)

			for intfName in lxc.containerInterfaces:
				if intfName in self.unmonitor:
					continue
				else:	
					intf = {'name': intfName, 'bw': 100, 'delay': '0ms'}
					node['interfaces'].append(intf)

		# print(json.dumps(self.info, indent=4, sort_keys=True))

		for link in net.links:
			try:
				B1 = link.params1['bw']
				B2 = link.params2['bw']
				d1 = link.params1['delay']
				d2 = link.params2['delay']

				# This is hell
				for host in self.info:
					for node in host['nodes']:
						for intf in node['interfaces']:
							if intf['name'] == link.intf1.name:
								intf['bw'] = B1
								intf['delay'] = d1
							if intf['name'] == link.intf2.name:
								intf['bw'] = B2
								intf['delay'] = d2

				B1 = B1 * 1e6
				B2 = B2 * 1e6
				B = B1 # TODO
				d = int(d1[:-2])
			except:
				B = 100e6
				d = 0

			self.links.append((link.intf1.name, link.intf2.name, B, d))


	def start(self):
		for host in self.info:
			try:
				self.sendInfo(host)
			except:
				info("*** Host %s unreachable\n" % host['IP'])


	def sendInfo(self, host):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		info("*** Connecting to agent at %s:%s...\n" % (host['IP'], AGENT_PORT))
		sock.connect((host['IP'], AGENT_PORT))
		info("*** Connection successful\n")

		info("*** Sending data to agent at %s:%s...\n" % (host['IP'], AGENT_PORT))
		data = host
		raw = pickle.dumps(data)

		i = 0
		N = len(raw)
		while i < N:
			if i+BUFFER < N:
				sent = raw[i: i+BUFFER]
			else:
				sent = raw[i:]
			i += BUFFER
			sock.send(sent)
		info("*** Data sent\n")

		info("*** Closing connection to %s:%s\n" % (host['IP'], AGENT_PORT))
		sock.close()

		return


	def wait(self):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.bind((MONITOR_IP, MONITOR_PORT))

		info("*** Waiting for agents...\n")
		sock.listen(1)

		N = len(self.info)
		for _ in range(N):
			conn, addr = sock.accept()
			conn.close()
			info("*** Host %s probed\n" % addr[0])
			del conn, addr

		sock.close()

		return


	def stop(self):
		for host in self.info:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.connect((host['IP'], AGENT_PORT))
			sock.close()

		return


	def receiveData(self):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.bind((MONITOR_IP, MONITOR_PORT))

		info("*** Waiting for data from agents...\n")
		sock.listen(1)
		self.data = {}

		N = len(self.info)
		for _ in range(N):
			conn, addr = sock.accept()

			info("*** Receiving data from %s...\n" % addr[0])
			raw = bytes()
			while True:
				rec = conn.recv(BUFFER)
				if not rec:
					break
				else:
					raw += rec

			self.data.update(pickle.loads(raw))

			conn.close()
			info("*** Data received from %s\n" % addr[0])
			del conn, addr

		sock.close()

		return

	def analyse(self):
		info("*** Analysing...\n")

		# for (intf1, intf2, B, d) in self.links:
		# 	db1 = self.data[intf1]
		# 	db2 = self.data[intf2]

		# 	if len(db1['packets_in'])*len(db1['packets_out'])*len(db2['packets_in'])*len(db2['packets_out']) == 0:
		# 		info("No packets in link %s--%s" % (intf1, intf2))
		# 		continue

		# 	col = Collector(db1, db2, B, d)
		# 	col.merge()
		# 	col.sort()
		# 	col.analyse()

		# 	if len(col.rtds) == 0:
		# 		info("No measurements available for link %s--%s" % (intf1, intf2))
		# 		continue

		# 	info("Link %s--%s: %i measurements\n" % (intf1, intf2, len(col.rtds)))

		# 	aes = [abs(col.rtds[i]-col.rtds_[i]) for i in range(length(col.rtds))]
		# 	aeqs = ["%.3fms" % np.percentile(aes, 10*i) for i in range(1, 11)]
		# 	info("\tMean Absolute Error is %.3fms\n" % np.mean(aes))
		# 	info("\tAbsolute Error Deciles are %s\n" % aeqs)


		# 	paes = [100*abs(col.rtds[i]-col.rtds_[i])/col.rtds_[i] for i in range(length(col.rtds)) if col.rtds_[i] != 0]
		# 	paeqs = ["%.2f%%" % np.percentile(paes, 10*i) for i in range(1, 11)]
		# 	info("\tMean Percentage Absolute Error is %.2f%%\n" % np.mean(paes))
		# 	info("\tPercentage Absolute Error Deciles are %s\n" % paeqs)
		for (intf1, intf2, B, d) in self.links:
			if intf1 in self.unmonitor or intf2 in self.unmonitor:
				continue

			db1 = self.data[intf1]
			db2 = self.data[intf2]

			if len(db1['packets_in'])*len(db1['packets_out'])*len(db2['packets_in'])*len(db2['packets_out']) == 0:
				continue

			print(B)
			col = Collector(db1, db2, B, d)
			col.merge()
			col.sort()
			col.analyse()

			if len(col.rtds) == 0:
				continue

			err_rel = [abs(col.rtds[i]-col.rtds_[i])/col.rtds_[i] for i in range(len(col.rtds))]
			err_abs = [abs(col.rtds[i]-col.rtds_[i])              for i in range(len(col.rtds))]
			queue = col.blens

			data = {"rtds": col.rtds, "rtds_": col.rtds_}
			raw = json.dumps(data)

			filename = "%s--%s" % (intf1, intf2)
			with open("/root/results/%s" % filename, 'w') as f:
				f.write(raw)



# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# ------------------------------_Analysis_-----------------------------
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


length = len

class Collector:
	def __init__(self, db1, db2, B=100e6, d=0):
		self.db1 = db1
		self.db2 = db2
		self.B = B
		self.d = d

		self.packets12 = []
		self.packets21 = []

		self.xids12 = list(set(self.db1['packets_out']) & set(self.db2['packets_in']))
		self.xids21 = list(set(self.db2['packets_out']) & set(self.db1['packets_in']))

	def merge(self):
		# 1 -> 2
		for xid in self.xids12:
			if length(self.db1['packets_out'][xid]) != length(self.db2['packets_in'][xid]):
				continue

			for i in range(min(length(self.db1['packets_out'][xid]), length(self.db2['packets_in'][xid]))):
				pin  = self.db2['packets_in'][xid][i]
				pout = self.db1['packets_out'][xid][i]
				(ts_in) = pin # us
				try:
					(ts_out, len, blen, plen, tau) = pout
				except:
					print(pout)
					continue

				packet = (xid, ts_out, ts_in, len, blen, plen, tau)
				self.packets12.append(packet)

		# 2 -> 1
		for xid in self.xids21:
			if length(self.db1['packets_in'][xid]) != length(self.db2['packets_out'][xid]):
				continue
				
			for i in range(min(length(self.db2['packets_out'][xid]), length(self.db1['packets_in'][xid]))):
				pin  = self.db1['packets_in'][xid][i]
				pout = self.db2['packets_out'][xid][i]
				(ts_in) = pin # us
				try:
					(ts_out, len, blen, plen, tau) = pout
				except:
					print(pout)
					continue

				packet = (xid, ts_out, ts_in, len, blen, plen, tau)
				self.packets21.append(packet)

	def sort(self):
		self.packets12.sort(key = lambda p: p[1])
		self.packets21.sort(key = lambda p: p[2])

	def analyse(self):
		B = self.B 
		d = self.d

		self.rtds = [] # ms
		self.rtds_ = [] # ms

		self.plens = []
		self.blens = []
		self.lens = []
		self.taus = []

		i = 0
		packet21 = self.packets21[0]
		for packet12 in self.packets12:
			while packet21[2] < packet12[1] and i < length(self.packets21)-1:
				i += 1
				packet21 = self.packets21[i]
			if packet21[2] < packet12[1]:
				break

			(xid12, ts_out12, ts_in12, len12, blen12, plen12, tau12) = packet12
			(xid21, ts_out21, ts_in21, len21, blen21, plen21, tau21) = packet21

			mes = (ts_in12 - ts_out12 + ts_in21 - ts_out21) * 1e-3 # ms

			# if mes < -100:
			# 	print(xid12, xid21, mes)

			# if mes < 0:
			# 	continue

			self.rtds.append(mes)

			blen = (blen12 + blen21)*8 # bits

			if plen12*8/B*1e6 < tau12:
				plen12 = 0
				tau12 = 0
			
			if plen21*8/B*1e6 < tau21:
				plen21 = 0
				tau21 = 0
			
			plen = (plen12 + plen21)*8 # bits

			len = (len12 + len21)*8 # bits

			tau = tau12 + tau21 # µs

			est = len*1e3/B + blen*1e3/B + (plen*1e3/B - tau*1e-3) + 2 * d

			self.blens.append(blen)
			self.plens.append(plen)
			self.lens.append(len)
			self.taus.append(tau)

			self.rtds_.append(est)

		# self.clean()

		# N = length(self.lens)

		# X = np.array([ [self.lens[i], self.blens[i], self.plens[i], self.taus[i]] for i in range(N) ])
		# y = np.array(self.rtds)

		# result = LinearRegression().fit(X, y)
		# print(result.score(X, y))
		# print(result.coef_)
		# print(result.intercept_)

	def clean(self, inf=5, sup=95):
		inf = np.percentile(self.rtds, inf)
		sup = np.percentile(self.rtds, sup)
		indices = [i for i in range(length(self.rtds)) if self.rtds[i]>inf and self.rtds[i]<sup]

		self.rtds = [self.rtds[i] for i in indices]
		self.lens = [self.lens[i] for i in indices]
		self.blens = [self.blens[i] for i in indices]
		self.plens = [self.plens[i] for i in indices]
		self.taus = [self.taus[i] for i in indices]
