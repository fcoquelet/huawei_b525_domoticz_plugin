# coding: utf-8
#from __future__ import unicode_literals
import hashlib
import base64
import sys
import collections,urllib.request as request, ssl, xml.etree.ElementTree as ET


class ClientMetaData(dict):
    COOKIE_LABEL = "Cookie"
    SESSION_ID_LABEL = "SessionID="
    VERIF_TOKEN_LABEL = "__RequestVerificationToken"
    
    def setSessionCookie(self, sessionId):
        if sessionId.startswith(ClientMetaData.SESSION_ID_LABEL):
            self[ClientMetaData.COOKIE_LABEL]=sessionId
        else:
            self[ClientMetaData.COOKIE_LABEL]=ClientMetaData.SESSION_ID_LABEL+sessionId

    def getSessionCookie(self):
        if ClientMetaData.COOKIE_LABEL in self:
            return self[ClientMetaData.COOKIE_LABEL]
        else:
           return None
           
    def clearSessionCookie(self):
        if ClientMetaData.COOKIE_LABEL in self:
            self.pop(ClientMetaData.COOKIE_LABEL)

    def refreshSessionCookieIfNeeded(self, requestInfo):
       new_cookie=requestInfo.get("Set-"+ClientMetaData.COOKIE_LABEL)
       if new_cookie:
           self.setSessionCookie(new_cookie)

    def refreshVerificationTokenIfNeeded(self, requestInfo):
        new_token=requestInfo.get(ClientMetaData.VERIF_TOKEN_LABEL)
        if new_token:
            self.setVerificationToken(new_token)

    
    def getVerificationToken(self):
        return self[ClientMetaData.VERIF_TOKEN_LABEL]

    def setVerificationToken(self,verifToken):
        self[ClientMetaData.VERIF_TOKEN_LABEL] = verifToken

    def hasVerificationToken(self):
        return ClientMetaData.VERIF_TOKEN_LABEL in self
    
    def clearVerificationToken(self):
        if ClientMetaData.VERIF_TOKEN_LABEL in self:
            self.pop(ClientMetaData.VERIF_TOKEN_LABEL)


class NotLoggedException(Exception):
    '''Exception to be thrown when action requires auth but client has not log on'''

class ConnectionException(Exception):
    '''Exception to be thrown when action requires auth but client has not log on'''

class Client:

    def __init__(self,modem_ip, no_ssl=True):
        self.MODEM_IP = modem_ip
        self.API_PATH = '/api/'
        self.PREV_API = None
        self.PREV_OBJ = None
        if no_ssl:
                ssl._create_default_https_context = ssl._create_unverified_context 
        self.metadata = ClientMetaData()
         
    # retrieve xml and if successful return root
    def sendReceive(self,api_call, data=None):
       
        #ssl._create_default_https_context = ssl._create_unverified_context
        # check previous call to avoid making multiple identical GET requests
        if api_call == self.PREV_API:
                return self.PREV_OBJ
        try:
                if data and not self.metadata.hasVerificationToken():
                    self.refreshToken()
                req = request.Request(url='http://'+self.MODEM_IP+self.API_PATH+api_call, headers=self.metadata)
                xmlobj = request.urlopen(req,data)
        except:
                print('[!] Error while making GET request for', api_call)
                raise ConnectionException("Error trying to reach "+ self.MODEM_IP)
        
        self.metadata.refreshVerificationTokenIfNeeded(xmlobj.info())
        self.metadata.refreshSessionCookieIfNeeded(xmlobj.info())
        # save current API call and XML obj
        self.PREV_API = api_call
        self.PREV_OBJ = ET.parse(xmlobj).getroot()
        xmlobj.close()
        return self.PREV_OBJ

    def hasToken(self):     
        return self.metadata.getSessionCookie() != None
        
    def getToken(self):
        self.headers = {}
        resp = self.sendReceive("webserver/SesTokInfo")
        self.metadata.setSessionCookie(resp.find("SesInfo").text)
        self.metadata.setVerificationToken(resp.find("TokInfo").text)
        return True
#api/webserver/SesTokInfo

    def refreshToken(self):
        self.metadata.clearVerificationToken()
        resp = self.sendReceive("webserver/token")
        token = resp.find('token').text
        self.metadata.setVerificationToken(token[32:])


    def login(self,saltedPassword):
        user = 'admin'
        
        req = ET.Element('request')
        ET.SubElement(req,'Username').text = user
        ET.SubElement(req,'password_type').text = '4'
        ET.SubElement(req,'Password').text=base64.b64encode(hashlib.sha256((user+saltedPassword+self.metadata.getVerificationToken()).encode('utf-8')).hexdigest().encode('utf-8')).decode()
        
        root = self.sendReceive('user/login',ET.tostring(req,encoding='UTF-8', method='xml'))
        self.metadata.clearVerificationToken()
        ET.dump(root)
        return root.text == 'OK' 

    def isLogged(self):
       root = self.sendReceive('user/state-login')
       return int(root.find('State').text)==0


# return data plan usage percentage
def get_usage(client):

        # retrieve download and upload traffic and convert them to MB
        root = client.sendReceive('monitoring/month_statistics')
        month_download = int(root.find('CurrentMonthDownload').text)/1048576
        month_upload = int(root.find('CurrentMonthUpload').text)/1048576

        # retrieve data plan limit and convert to MB
        root = client.sendReceive('monitoring/start_date')
        data_limit = root.find('DataLimit').text

        # convert DataLimit suffix GB to MB
        if data_limit.endswith('GB'):
                data_limit = int(data_limit[:-2])*1024
        else:
                data_limit = int(data_limit[:-2])

        # return percentage
        return collections.namedtuple('usage',['download','upload','consumption'])(int(month_download),int(month_upload),int(round(((month_upload + month_download) / data_limit) * 100)))

        
def send_sms(client, tels, text):
    if not client.isLogged():
        raise NotLoggedException('Need to be logged to send SMS')
    req = ET.Element('request')
    ET.SubElement(req,'Index').text = '-1'
    phones=ET.SubElement(req,'Phones')
    for tel in tels:
        ET.SubElement(phones,'Phone').text=tel
    ET.SubElement(req,'Content').text = text
    ET.SubElement(req,'Length').text = str(len(text))
    ET.SubElement(req,'Reserved').text = "1"
    ET.SubElement(req,'Date').text = "2017-10-01 23:01:30"
    root = client.sendReceive('sms/send-sms',ET.tostring(req, encoding="UTF-8", method="xml"))
    return root.text == "OK"

def is_data_enabled(client):
    root = client.sendReceive('dialup/mobile-dataswitch')
    return int(root.find('dataswitch').text)==1

def enable_data(client,enable=True):
    if not client.isLogged():
        raise NotLoggedException('Need to be logged to switch data')
    req = ET.Element('request')
    ET.SubElement(req,'dataswitch').text = str(int(enable))
    root = client.sendReceive('dialup/mobile-dataswitch',ET.tostring(req, encoding="UTF-8", method="xml"))
    return root.text == "OK"

# return signal strength percentage
def get_signal(client):
        root = client.sendReceive('monitoring/status')
        return int(root.find('SignalIcon').text)

