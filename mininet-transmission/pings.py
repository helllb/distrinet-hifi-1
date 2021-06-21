from mininet.log import info
from mininet.topo import Topo
from mininet.link import TCLink

class PingsTopo(Topo):
	def build(self, bw=10, delay="1ms"):
		h1 = self.addHost("h1")
		h2 = self.addHost("h2")
		s1 = self.addSwitch("s1")
		s2 = self.addSwitch("s2")
		self.addLink(h1, s1)
		self.addLink(h2, s2)
		self.addLink(s1, s2, bw=bw)

def pings(net):
	h1 = net.get('h1')
	h2 = net.get('h2')

	info('*** Pinging...\n')

	sizes = '{' + ','.join([str(s) for s in range(100, 1401, 100)]) + '}'
	cmd = 'for s in %s; do ping %s -c 1000 -i 0.001 -s $s > /tmp/ping_$s; done' % (sizes, h2.IP())
	h1.cmd(cmd)


tests = {'pings': pings}
topos = {'pings': PingsTopo}
