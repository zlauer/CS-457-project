import getopt
import sys
import socket


## argument handling
args = sys.argv[1:]
options = "hip:"

try:
    arguments, values = getopt.getopt(args, options)
    for currentArg, currentVal in arguments:
        if currentArg in ("-h"):
            with open("help.txt", "r") as file:
                print(file.read())
        elif currentArg in ("-i"):
            print("server dns name")
        elif currentArg in ("-p"):
            print("port number")
except getopt.error as err:
    print(str(err))