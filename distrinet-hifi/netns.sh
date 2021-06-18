pid=$(lxc info $1 | grep Pid | awk '{print $2}')

ln -sf /proc/$pid/ns/net /var/run/netns/$pid

echo $pid
