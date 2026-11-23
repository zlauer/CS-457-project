### Topology Screenshot:
![CML topology](https://github.com/zlauer/CS-457-project/blob/main/sprint-4/images/topology.png?raw=true)

This is an image detailing what the actual topology of my Cisco lab looks like for my project.  There are custom node names for each of them including client1-ZL, client2-ZL, R1-ZL(R for router), and also server-ZL.

### CLI outputs

These are screenshots detailing outputs, underlined in green, for specific intputs:
```
# On Client 1 and Client 2 Consoles (Alpine Linux):
sudo ip link set eth0 up
sudo udhcpc -i eth0

# Verify assigned IP, default gateway route, and DNS resolver:
ip addr show eth0
ip route
cat /etc/resolv.conf
```
as well as pinging each client.

**client1-ZL**
![udhcpc, ip addr show, ip route](https://github.com/zlauer/CS-457-project/blob/main/sprint-4/images/client1%20udchcp.png?raw=true)
![ping](https://github.com/zlauer/CS-457-project/blob/main/sprint-4/images/client1%20ping.png?raw=true)

**client2-ZL**
![udhcpc, ip addr show, ip route](https://github.com/zlauer/CS-457-project/blob/main/sprint-4/images/client2%20udchcp.png?raw=true)
![ping](https://github.com/zlauer/CS-457-project/blob/main/sprint-4/images/client2%20ping.png?raw=true)

### Wireshark DNS output
Here are each of the DNS protocols that were thrown.

![wireshark](https://github.com/zlauer/CS-457-project/blob/main/sprint-4/images/dns%20protocol%20wireshark.png?raw=true)
**this** is a screenshot from sprint_4_packet_capture.pcap.


![dns wireshark](https://github.com/zlauer/CS-457-project/blob/main/sprint-4/images/dns%20server%20lookup.png?raw=true)
**this** is a screenshot from sprint_4_dns_lookup when using the command nslookup -type=A server.[yourlastname].edu.
