from mininet.log import info

def pings(net):
	h1 = net.get('h1')
	h2 = net.get('h2')

	info('*** Pinging...\n')

	sizes = '{' + ','.join([str(s) for s in range(100, 1401, 100)]) + '}'
	cmd = 'for s in %s; do ping %s -c 1000 -i 0.001 -s $s > /tmp/ping_$s; done' % (sizes, h2.IP())
	h1.cmd(cmd)


tests = {'pings': pings}
