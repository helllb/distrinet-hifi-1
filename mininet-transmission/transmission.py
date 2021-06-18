#!/usr/bin/env python3

from asynciojobs import Scheduler
from apssh import SshNode, SshJob, Run, Push, Pull

from pingparsing import PingParsing

from numpy import mean, std
import matplotlib.pyplot as plt

GATEWAY = 'faraday.inria.fr'
SLICE = 'inria_distrinet'
HOSTNAME = 'fit01'

faraday = SshNode(hostname=GATEWAY, username=SLICE, verbose=False)
host = SshNode(gateway=faraday, hostname=HOSTNAME, username='root', verbose=False)

scheduler = Scheduler()

check_lease = SshJob (
        node = faraday,
        critical = True,
        command = Run('rleases --check'),
        scheduler = scheduler
)

pings = SshJob (
		node = host,
		critical = True,
		command = Run('mn --custom=pings.py --link=tc,bw=10 --test=pings'),
		scheduler = scheduler,
		required = check_lease
)


def get_rtts(filename):
	parser = PingParsing()

	rtts = []

	with open(filename, 'r') as file:
		raw = file.read()
		stats = parser.parse(raw)

	for reply in stats.icmp_replies:
		rtt = reply['time']
		rtts.append(rtt)

	return rtts


if __name__ == '__main__':
	ok = scheduler.orchestrate()

	ss = []
	rttss = []
	sizes = []
	mus = []
	sigs = []

	for s in range(100, 1401, 100):
		size = 2*(s+48)
		sizes.append(size)

		filename = 'ping_%i' % s
		rtts = get_rtts(filename)

		ss.extend(1000*[size])
		rttss.extend(rtts)

		mu = mean(rtts)
		sig = std(rtts)
		mus.append(mu)
		sigs.append(sig)

	mus_ = [size*8/10e6 * 1e3 for size in sizes]

	plt.scatter(ss, rttss, 1, label='Measured RTD (individual)')
	plt.plot([], [])
	plt.errorbar(sizes, mus, yerr=sigs, label='Measured RTD (average)')
	plt.plot(sizes, mus_, format='--', label='Estimated RTD')

	plt.show()
