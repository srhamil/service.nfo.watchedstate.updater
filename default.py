'''
*  This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) License.
*
*
*  To view a copy of this license, visit
*
*  English version: http://creativecommons.org/licenses/by-nc-sa/4.0/
*  German version:  http://creativecommons.org/licenses/by-nc-sa/4.0/deed.de
*
*  or send a letter to Creative Commons, 171 Second Street, Suite 300, San Francisco, California, 94105, USA.
'''


import xbmc
import xbmcvfs
import xbmcaddon
import socket
import json
import xml.etree.ElementTree as ET
from os import path
from os import stat as osstat



addon = xbmcaddon.Addon('service.nfo.watchedstate.updater')
addon_name = addon.getAddonInfo('name')

delay = '4000'
logo = 'special://home/addons/service.nfo.watchedstate.updater/icon.png'


class NFOWatchedstateUpdater():
    def __init__(self):
        self.methodDict = {"VideoLibrary.OnUpdate": self.VideoLibraryOnUpdate,
                          }

        self.XBMCIP = addon.getSetting('xbmcip')
        self.XBMCPORT = int(addon.getSetting('xbmcport'))
        
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setblocking(1)
        xbmc.sleep(int(delay))
        try:
            self.s.connect((self.XBMCIP, self.XBMCPORT))
        except Exception as e:
            xbmc.executebuiltin('Notification(%s, Error: %s, %s, %s)' %(addon_name, str(e), delay, logo) )
            xbmc.sleep(int(delay))
            xbmc.executebuiltin('Notification(%s, Please check JSONRPC settings, %s, %s)' %(addon_name, delay, logo) )
            xbmc.sleep(int(delay))
            #xbmc.executebuiltin('ActivateWindow(10018)')
            exit(0)
                

    def handleMsg(self, msg):
        jsonmsg = json.loads(msg)        
        method = jsonmsg['method']
        if method in self.methodDict:
            methodHandler = self.methodDict[method]
            methodHandler(jsonmsg)
            

    def listen(self):
        currentBuffer = []
        msg = ''
        depth = 0
        while not xbmc.abortRequested:
            chunk = self.s.recv(1)
            currentBuffer.append(chunk)
            if chunk == '{':
                depth += 1
            elif chunk == '}':
                depth -= 1
                if not depth:
                    msg = ''.join(currentBuffer)
                    self.handleMsg(msg)
                    currentBuffer = []
        self.s.close()


    def VideoLibraryOnUpdate(self, jsonmsg):        
        xbmc.log("{0} message: {1}".format(addon_name,str(jsonmsg)),xbmc.LOGDEBUG)
        itemid = None
        itemtype = None
        itemplaycount = None
        try:
            itemid = jsonmsg["params"]["data"]["item"]["id"]
            itemtype = jsonmsg["params"]["data"]["item"]["type"]
            itemplaycount = jsonmsg["params"]["data"]["playcount"]
        except Exception :
            xbmc.log("{0} ignoring, not a playcount update".format(addon_name),xbmc.LOGINFO)
            return

        if ( itemid and itemtype and itemplaycount is not None ): 
            xbmc.log("{0} itemplaycount update message  itemid {1}  itemtype {2}  itemplaycount {3}".format(addon_name,str(itemid),str(itemtype),str(itemplaycount)),xbmc.LOGDEBUG)
     
            if itemtype == u'movie':
                msg = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.GetMovieDetails","params":{"movieid":%d,"properties":["file"]},"id":1}' %(itemid) )
                jsonmsg = json.loads(msg)

                filepath = jsonmsg["result"]["moviedetails"]["file"]

                self.updateNFO(filepath, itemplaycount)


            ##When a season is marked as un-/watched, all episodes are edited
            if itemtype == u'episode':
                msg = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.GetEpisodeDetails","params":{"episodeid":%s,"properties":["file"]},"id":1}' %(str(itemid)) )
                jsonmsg = json.loads(msg)

                filepath = jsonmsg["result"]["episodedetails"]["file"]

                self.updateNFO(filepath, itemplaycount)


            if itemtype == u'tvshow':
                msg = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.GetTVShowDetails","params":{"tvshowid":%s,"properties":["file"]},"id":1}' %(str(itemid)) )
                jsonmsg = json.loads(msg)

                filepath = path.join(jsonmsg["result"]["tvshowdetails"]["file"], "tvshow.nfo")

                self.updateNFO(filepath, itemplaycount)

               

    def locateNfoFile(self, filepath):            
        # handle the alternate location of movie.nfo which Kodi supports but does not recommend using
        filepath = filepath.replace(path.splitext(filepath)[1], '.nfo')
        filepath2 = filepath.replace(path.split(filepath)[1], 'movie.nfo')
        if xbmcvfs.exists(filepath) == False and xbmcvfs.exists(filepath2):
            filepath = filepath2
        xbmc.log("{0} updating {1}".format(addon_name,filepath), xbmc.LOGINFO)
        return filepath

    def readFile(self,filepath):
        sFile = xbmcvfs.File(filepath)
        currentBuffer = []
        msg = ''
        while True:
            buf = sFile.read(1024)
            currentBuffer.append(buf)
            if not buf:
                msg = ''.join(currentBuffer)                    
                break

        sFile.close()
        return msg

    def parseXml(self,xml):
            try:
                tree = ET.ElementTree(ET.fromstring(xml))
                return tree
            except Exception as err:
                xbmc.log("{0} bad xml: {1}".format(addon_name,str(err)), xbmc.LOGDEBUG)
            return None
      
 

    def setElementText(self, element, value):
        xbmc.log("{0} setElementText  {1}, {2}, ".format(addon_name,str(element),str(value)), xbmc.LOGDEBUG)
        currentValue = element.text
        if ( str(value) == currentValue ): return False
        element.text = str(value)
        return True

    def updateNFO(self, filepath, playcount):
        dirty = False
        filepath = self.locateNfoFile(filepath)
        notificationsWanted = addon.getSetting('notification') == 'true'

        if xbmcvfs.exists(filepath):
            xml = self.readFile(filepath)
            if not xml:
                xbmc.log("{0} NFO is not readable  {1}".format(addon_name,filepath), xbmc.LOGINFO)
                if notificationsWanted:  xbmc.executebuiltin('Notification(%s, NFO not readable, %s, %s)' %(addon_name, delay, logo) )
                return
             
            tree=self.parseXml(xml)
            if tree is None:
                xbmc.log("{0} NFO is not XML  {1}".format(addon_name,filepath), xbmc.LOGINFO)
                if notificationsWanted: xbmc.executebuiltin('Notification(%s, NFO is not XML, %s, %s)' %(addon_name, delay, logo) )
                return

            root = tree.getroot()
            if root is None:
                xbmc.log("{0} root element not found".format(addon_name), xbmc.LOGINFO)
                if notificationsWanted: xbmc.executebuiltin('Notification(%s, NFO unexpected contents, %s, %s)' %(addon_name, delay, logo) )
                return
 
            p = self.findOrCreateElement(root,'playcount', True)
            dirty = self.setElementText(p, playcount) or dirty
 
            if addon.getSetting('changewatchedtag') == 'true':
                w = self.findOrCreateElement(root,'watched', addon.getSetting('createwatchedtag') == 'true')
                if (w is not None):
                    dirty = self.setElementText(w,   playcount > 0 and 'True' or 'False' ) or dirty
                

            if ( dirty ):
                self.prettyPrintXML(root)
                xml = ET.tostring(root, encoding='UTF-8')
                if not xml:
                    xbmc.log("{0} NFO XML creation failed".format(addon_name), xbmc.LOGINFO)
                    if notificationsWanted: xbmc.executebuiltin('Notification(%s, NFO XML creation failed, %s, %s)' %(addon_name, delay, logo) )
                    return
                xbmc.log("{0} xml is {1}".format(addon_name, str(xml)), xbmc.LOGDEBUG)
 
                if self.writeFile(filepath, xml):
                    xbmc.log("{0} succesfully updated {1}".format(addon_name, filepath), xbmc.LOGDEBUG)
                    if notificationsWanted: xbmc.executebuiltin('Notification(%s, NFO updated, %s, %s)' %(addon_name, delay, logo) )
                else:
                    if notificationsWanted: xbmc.executebuiltin('Notification(%s, NFO not updated; write issue, %s, %s)' %(addon_name, delay, logo) )
            else:
                xbmc.log("{0} no changes to the NFO file are needed".format(addon_name),xbmc.LOGDEBUG)

        else:
            xbmc.log("{0} NFO not found {1}".format(addon_name, filepath), xbmc.LOGINFO)
            if notificationsWanted:
                xbmc.executebuiltin('Notification(%s, NFO File not found, %s, %s)' %(addon_name, delay, logo) )

    def findOrCreateElement( self,  parent, elementName, okToCreate):
        xbmc.log("{0} findOrCreateElement  {1}, {2}, {3} ".format(addon_name,str(parent),str(elementName),str(okToCreate)), xbmc.LOGINFO)
        result = parent.find(elementName)
        if result == None and okToCreate:
            result = ET.SubElement(parent,elementName)
        return result

    def writeFile(self, filepath, contents):
        notificationsWanted = addon.getSetting('notification') == 'true'
        try:
            dFile = xbmcvfs.File(filepath, 'w')
            dFile.write(contents) ##String msg or bytearray: bytearray(msg)
            dFile.close()
            return True
        except Exception as e:
            xbmc.log("{0} I/O Error writing {1}, {2}".format(addon_name, filepath, str(e)),xbmc.LOGINFO)
            if notificationsWanted: xbmc.executebuiltin('Notification(%s, Write IO Error %s, %s)' %(addon_name, delay, logo) )
        return False
            


    def prettyPrintXML(self, elem, level=0):
        i = '\n' + level * '  '
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.prettyPrintXML(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i


if __name__ == '__main__':
    WU = NFOWatchedstateUpdater()
    WU.listen()
    del WU
