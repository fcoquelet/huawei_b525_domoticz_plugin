# coding: utf-8
#from __future__ import unicode_literals
import vcr
import hashlib
import base64
import sys
import collections,urllib2, xml.etree.ElementTree as ET

MODEM_IP = '***REMOVED***.252'
API_PATH = '/api/'
PREV_API = ''
SALTED_PASSWD = u'***REMOVED***'
PREV_OBJ = None
COOKIE = None
TOKEN = None

# retrieve xml and if successful return root
def get_xml_root(api_call, header_context={}, data=None):
        # check previous call to avoid making multiple identical GET requests
        global PREV_API
        global PREV_OBJ
        if api_call == PREV_API:
                return PREV_OBJ
        try:
                if  data and not '__RequestVerificationToken' in header_context:
                    header_context = refresh_token(header_context)
                req = urllib2.Request(url='http://'+MODEM_IP+API_PATH+api_call, headers=header_context)
                xmlobj = urllib2.urlopen(req,data)
        except:
                print('[!] Error while making GET request for', api_call)
                exit(1)
        new_cookie=xmlobj.info().getheader("Set-Cookie")
        if (new_cookie):
            header_context["Cookie"] = new_cookie
            print('New cookie has been set')
        new_token=xmlobj.info().getheader('__RequestVerificationToken')
        if (new_token):
            header_context['__RequestVerificationToken']=new_token
        # save current API call and XML obj
        PREV_API = api_call
        PREV_OBJ = ET.parse(xmlobj).getroot()
        return collections.namedtuple('response','xmlroot,headers')(PREV_OBJ,header_context)

# return value in specified xml tag
def get_value(root, tag):
        value = root.find(tag)
        if value is not None:
                return value.text

def getToken():
        header_context = {}
        resp = get_xml_root("webserver/SesTokInfo")
        print resp.xmlroot
        header_context["Cookie"] = "SessionID_R3="+get_value(resp.xmlroot,"SesInfo")
        header_context["__RequestVerificationToken"] = get_value(resp.xmlroot,"TokInfo")
        return header_context
#api/webserver/SesTokInfo

def refresh_token(header_context):
        if "__RequestVerificationToken" in header_context:
            header_context.pop("__RequestVerificationToken")
        resp = get_xml_root("webserver/token",header_context)
        token = get_value(resp.xmlroot,'token')
        resp.headers["__RequestVerificationToken"] = token[32:]
        return resp.headers

# return data plan usage percentage
def get_usage(header_context={}):
        # modem will not allow API calls if someone is logged in
        root = get_xml_root('user/state-login',header_context)
        state = int(get_value(root.xmlroot,'State'))
        user = get_value(root.xmlroot, 'Username')
        # if state is -1 and username is not empty we cannot make the API call
        if (state == -1) and (user is not None):
                print('[!] Cannot make API calls: %s is logged in' % user)
                exit(1)

        # retrieve download and upload traffic and convert them to MB
        root = get_xml_root('monitoring/month_statistics',header_context).xmlroot
        month_download = int(int(get_value(root, 'CurrentMonthDownload'))/1048576)
        month_upload = int(int(get_value(root, 'CurrentMonthUpload'))/1048576)

        # retrieve data plan limit and convert to MB
        root = get_xml_root('monitoring/start_date',header_context).xmlroot
        data_limit = get_value(root, 'DataLimit')

        # convert DataLimit suffix GB to MB
        if data_limit[2:] == 'GB':
                data_limit = int(data_limit[:-2])*1024
        else:
                data_limit = int(data_limit[:-2])

        # return percentage
        return int(round((float(month_upload + month_download) / data_limit) * 100))




def login(header_context):
    user = 'admin'
    global SALTED_PASSWD
    req = ET.Element('request')
    ET.SubElement(req,'Username').text = user
    ET.SubElement(req,'password_type').text = '4'
    ET.SubElement(req,'Password').text=base64.b64encode(hashlib.sha256(user+SALTED_PASSWD+header_context['__RequestVerificationToken']).hexdigest())
    root = get_xml_root('user/login',header_context,ET.tostring(req,encoding='UTF-8', method='xml'))
    root.headers.pop('__RequestVerificationToken')
    return root.headers

def is_logged(header_context):
     root = get_xml_root('user/state-login',header_context)
     return int(root.xmlroot.find('State').text)==0
        
def send_sms(tel, text, header_context):
    req = ET.Element('request')
    ET.SubElement(req,'Index').text = '-1'
    phones=ET.SubElement(req,'Phones')
    ET.SubElement(phones,'Phone').text=tel
    ET.SubElement(req,'Content').text = text
    ET.SubElement(req,'Length').text = str(len(text))
    ET.SubElement(req,'Reserved').text = "1"
    ET.SubElement(req,'Date').text = "2017-10-01 23:01:30"
    root = get_xml_root('sms/send-sms',header_context,ET.tostring(req, encoding="UTF-8", method="xml"))
    return None    


# return signal strength percentage
def get_signal(header_context = {}):
        root = get_xml_root('monitoring/status',header_context).xmlroot
        return int(get_value(root, 'SignalIcon'))

# return battery percentage
def get_battery(header_context = {}):
        root = get_xml_root('monitoring/status',header_context)
        return int(get_value(root, 'BatteryPercent'))

# return number of current wifi users
def get_wifi_users():
        root = get_xml_root('monitoring/status',header_context)
        return int(get_value(root, 'CurrentWifiUser'))

with vcr.use_cassette('fixtures/vcr_cassettes/huawei.yaml'):
    headers = getToken()
    print headers
    headers = refresh_token(headers)
    headers = login(headers)
    print is_logged(headers)
    send_sms("***REMOVED***","I m so happy to see you !", headers)
    print is_logged(headers)
    print('DATA PLAN USAGE: {}%'.format(get_signal(headers)))

