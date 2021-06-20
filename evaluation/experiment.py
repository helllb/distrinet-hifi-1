from asynciojobs import Scheduler
from apssh import SshNode, SshJob, Run, Push, Pull

from argparse import ArgumentParser

from datetime import datetime
import json
import numpy as np
import matplotlib.pyplot as plt


# ------------- Parsing arguments -------------

parser = ArgumentParser()
parser.add_argument("--setup", action="store_true")
parser.add_argument("--experiment", action="store_true")
parser.add_argument("--download", action="store_true")
parser.add_argument("--analyse", action="store_true")
parser.add_argument("--nclients", "-N", type=int, default=2, help="number of clients, default = 2")
args = parser.parse_args()

setup = args.setup
download = args.download
experiment = args.experiment
analyse = args.analyse
nclients = args.nclients




# ------------- Some constants -------------

PATH = "./"
SLICE = "inria_distrinet"

hostname1 = 'fit01'
hostname2 = 'fit03'

# nclients = 4





# ------------- Nodes -------------

faraday = SshNode(hostname="faraday.inria.fr", username=SLICE, verbose=False)
worker1 = SshNode(gateway=faraday, hostname=hostname1, username="root", verbose=False)
worker2 = SshNode(gateway=faraday, hostname=hostname2, username="root", verbose=False)

scheduler = Scheduler()





# ------------- Begin -------------

check_lease = SshJob (
	node = faraday,
	scheduler = scheduler,
	critical = True,
	command = Run("rleases --check")
)

requirement = check_lease

if setup:
	setup1 = SshJob (
		node = faraday,
		scheduler = scheduler,
		critical = True,
		commands = [
			Run("rload -i u18.04-bcc_distrinet %s" % hostname1),
			Run("rwait %s --timeout 120" % hostname1)
		],
		required = requirement
	)

	setup2 = SshJob (
		node = faraday,
		scheduler = scheduler,
		critical = True,
		commands = [
			Run("rload -i u18.04-bcc_distrinet_worker %s" % hostname2),
			Run("rwait %s --timeout 120" % hostname1)
		],
		required = requirement
	)

	ip1 = SshJob (
		node = worker1,
		scheduler = scheduler,
		critical = True,
		commands = [
			Run("ifconfig data 10.10.20.1/24 up"),
			Run("mkdir /root/results || true")
		],
		required = setup1
	)

	ip2 = SshJob (
		node = worker2,
		scheduler = scheduler,
		critical = True,
		command = Run("ifconfig data 10.10.20.3/24 up"),
		required = setup2
	)

	requirement = (ip1, ip2)


if experiment:
	agent1 = SshJob (
		node = worker1,
		scheduler = scheduler,
		critical = True,
		commands = [
			Run("cd experiment/ ; nohup python3 agent.py < /dev/null > worker1.debug 2>&1 &"),
			Run("echo agent 1 started")
		],
		required = requirement
	)

	agent2 = SshJob (
		node = worker2,
		scheduler = scheduler,
		critical = True,
		commands = [
			Run("cd experiment/ ; nohup python3 agent.py > worker2.debug 2>&1 < /dev/null &"),
			Run("echo agent 2 started")
		],
		required = requirement
	)

	experiment = SshJob (
		node = worker1,
		scheduler = scheduler,
		commands = [
			Run('nohup ryu-manager', 
				'/usr/lib/python3/dist-packages/ryu/app/simple_switch_13.py',
				'> /dev/null 2> worker1.debug < /dev/null &'),
			Run('rm /root/results/* || true'),
			Run('cd ~/Distrinet/mininet;',
				'export PYTHONPATH=$PYTHONPATH:mininet:;',
				'python3 bin/dmn',
				'--bastion=10.10.20.1',
				'--workers="10.10.20.1,10.10.20.3"', 
				'--controller=lxcremote,ip=192.168.0.1',
				'--custom=custom/experiment.py',
				'--topo=exptopo,%i' % nclients,
				'--test=experiment,100M,20'),
			Run('pkill -SIGKILL ryu'),
		],
		critical = True,
		required = (agent1, agent2),
	)

	requirement = experiment,


if download:
	download = SshJob (
		node = worker1,
		scheduler = scheduler,
		command = Pull(remotepaths=["/root/results"], localpath=PATH, recurse=True),
		critical = True,
		required = requirement
	)

	requirement = download

ok = scheduler.orchestrate()





# ------------- Analysis -------------

def convert(strtime):
	dt = datetime.strptime(strtime, "%H:%M:%S.%f").time()
	h, m, s, mu = dt.hour, dt.minute, dt.second, dt.microsecond 
	mus = mu + 1000000*(s + 60*(m + 60*h))
	return mus * 1e-6

def get_fct(filename):
	with open(filename, 'r') as f:
		line1 = f.readline()[:-1]
		line2 = f.readline()[:-1]
		f.close()

	t1 = convert(line1)
	t2 = convert(line2)

	return t2 - t1

def get_fcts(nclients):
	fcts = ([], [])
	for i in range(nclients):
		try:
			j = i + 2
			filename = "results/h%i.out" % j
			fct = get_fct(filename)

			h =  (i + 1) % 2
			fcts[h].append(fct)
		except:
			h =  (i + 1) % 2
			print("Warning Mininet error: client %i (host %i) has not generated a flow" % (i+1, h))

	return fcts

def plot_fcts(fcts):
	plt.subplot(211)

	nclients = len(fcts[0])+len(fcts[1])
	plt.boxplot(fcts, labels=["Host 1", "Host 2"], showfliers=False)

	plt.ylabel("FCT (s)")
	plt.title("Flow Completion Times (N = %i)" % nclients)




def get_rel(filename):
	with open(filename, 'r') as f:
		raw = f.read()
		data = json.loads(raw)
	rel = [d*100 for d in data['rel']]
	return rel

def clean_extremes(xs, inf=1, sup=99):
	inf = np.percentile(xs, inf)
	sup = np.percentile(xs, sup)

	xs_ = [x for x in xs if x > inf and x < sup]
	return xs_

def get_cdf(xs, bins=100):
	count, bins_count = np.histogram(xs, bins=bins)
	pdf = count / sum(count)
	cdf = np.cumsum(pdf)

	return list(bins_count[1:]), list(cdf)

def plot_errors(nclients):
	plt.subplot(212)

	# This is hell
	M = 0
	for i in range(nclients):
		try:
			j = i + 2
			filename = "results/s1-eth%i--h%i-eth0" % (j, j)

			rel = get_rel(filename)
			rel = clean_extremes(rel)

			bins_count, cdf = get_cdf(rel)

			M = max(M, bins_count[-1])
		except:
			continue

	for i in range(nclients):
		try:
			j = i + 2
			filename = "results/s1-eth%i--h%i-eth0" % (j, j)

			rel = get_rel(filename)
			rel = clean_extremes(rel)

			bins_count, cdf = get_cdf(rel)

			if i % 2:
				col = "red"
			else:
				col = "blue"
				
			plt.plot(bins_count+[M], cdf+[1], color=col)

		except:
			h =  (i + 1) % 2
			print("Warning Mininet error: client %i (host %i) has not generated a flow" % (i+1, h))

	plt.plot([], [], color="blue", label="Overlay links")
	plt.plot([], [], color="red", label="Local links")
	plt.legend()

	plt.title("Percentage Absolute Error CDFs")
	plt.xlabel("PAE (%)")

if analyse:
	fcts = get_fcts(nclients)
	plot_fcts(fcts)

	plot_errors(nclients)

	plt.show()
