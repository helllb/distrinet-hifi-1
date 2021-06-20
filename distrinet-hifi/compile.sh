netns=$1
dev=$2
rate=$3
delay=$4



# clang -O2 -emit-llvm -c foo.c -o - | llc -march=bpf -mcpu=probe -filetype=obj -o foo

ip netns exec $netns tc qdisc del dev $dev root
# ip netns exec $netns tc qdisc del dev $dev ingress

ip netns exec $netns tc qdisc add dev $dev root handle 1: htb
ip netns exec $netns tc class add dev $dev parent 1: classid 1:10 htb rate $rate
ip netns exec $netns tc filter add dev $dev parent 1: bpf da obj /root/experiment/foo sec egress flowid 1:10
ip netns exec $netns tc qdisc add dev $dev parent 1:10 handle 2: netem delay $delay

ip netns exec $netns tc qdisc add dev $dev ingress handle ffff:
ip netns exec $netns tc filter add dev $dev parent ffff: bpf da obj /root/experiment/foo sec ingress
