import paho.mqtt.publish as publish

while True:
    pub = input()
    if pub == "0":
        pub = "ALLOFF"
    elif pub == "1":
        pub = "(0,0,0)"
    elif pub == "2":
        pub = "(1,1,10)"
    publish.single("void", pub, hostname="www.home")