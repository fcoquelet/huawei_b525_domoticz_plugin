"""
<plugin key="HuaweiModemLte" name="Huawei B525 LTE modem" author="***REMOVED***" version="0.0.1">
<params>
    <param field="Address" label="IP Address" required="true" default="192.168.8.1" />
	<param field="Mode1" label="Polling interval" default="10" width="40px" required="true" />
    <param field="Password" label="Password" required="true" />
</params>
</plugin>
"""
import Domoticz
import base64
import hashlib
import time
import huawei_urllib

class HuaweiPlugin:
    DATA_SWITCH = 1
    DATA_PLAN_CONSUMPTION = 2

    def __init__(self):
        self.saltedPassword = None
        self.nextUpdate = None
        return

    def onStart(self):
        Domoticz.Log("onStart called")

        if len(Devices)==0:
            Domoticz.Device(Name="Data Switch",Unit=HuaweiPlugin.DATA_SWITCH,TypeName="Switch").Create()
            Domoticz.Device(Name="Data Plan consumption",Unit=HuaweiPlugin.DATA_PLAN_CONSUMPTION,TypeName="Percentage").Create()
        Domoticz.Log("Calculating salted Password")
        self.saltedPassword = base64.b64encode(hashlib.sha256(Parameters["Password"].encode('utf-8')).hexdigest().encode('utf-8')).decode()
        self.nextUpdate = time.time()
        self.client = huawei_urllib.Client(Parameters["Address"])
        self.refresh()


    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")

    def onMessage(self, Connection, Data, Status, Extra):
        Domoticz.Log("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        #Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        if Unit == HuaweiPlugin.DATA_SWITCH:
            if not self.client.isLogged():
                self.client.getToken()
                self.client.login(self.saltedPassword)
            try:
                enable=(Command=="On")
                if huawei_urllib.enable_data(self.client,enable):
                    self.updateDataSwitch(enable)
            except HuaweiPlugin.NotLoggedException:
                Domoticz.error("Unable to log on")
        

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")

    def onHeartbeat(self):
        currentTime = time.time()
        if self.nextUpdate < currentTime:
            #Compute next running time
            self.nextUpdate = int(currentTime) + int(Parameters["Mode1"])
            self.refresh()
	
    def refresh(self):
        if self.client.isLogged() or self.client.getToken():
            self.updateDataSwitch(huawei_urllib.is_data_enabled(self.client))
            percent = huawei_urllib.get_usage(self.client)
            Domoticz.Log(str(percent))
            Devices[HuaweiPlugin.DATA_PLAN_CONSUMPTION].Update(percent,str(percent))
        else:
            Domoticz.Error("Unable to reach the Huawei Modem ({})".format(Parameters["Address"]))
            
    def updateDataSwitch(self, enabled):
        if enabled:
            Domoticz.Log("On")
            Devices[HuaweiPlugin.DATA_SWITCH].Update(1,"On")
        else:
            Domoticz.Log("Off")
            Devices[HuaweiPlugin.DATA_SWITCH].Update(0,"Off")
			

global _plugin
_plugin = HuaweiPlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data, Status, Extra):
    global _plugin
    _plugin.onMessage(Connection, Data, Status, Extra)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

