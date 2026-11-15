import getopt
import sys
import socket



try:
    server_ip = socket.gethostbyname(args.hostname)
except socket.gaierror as e:
    print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
    print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
    sys.exit(1)