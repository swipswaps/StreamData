"""
    load.py
    This script loads the tables for the StreamData RestAPI
    ======
    
    Copyright 2019 Moy IT Solutions
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
      http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""
import urllib.request
import mysql.connector
import json
import ssl
import appconfig

mydb = mysql.connector.connect(
  host=appconfig.db_host,
  user=appconfig.db_user,
  password=appconfig.db_user_password,
  database=appconfig.db_name,
  auth_plugin='mysql_native_password'
)

def main():
    print('Clearing Staging Tables')
    truncateStagingTables()
    print('Downloading stream data...')
    regions = ['us', 'ca', 'uk', 'au']
    for region in regions:
        downloadStreamData(region)
        loadStagingTables(region)
    print('Downloading title database')
    downloadTitleIDs()
    loadRegions()
    loadSites()
    loadTitles()
    loadMALIds()
    loadLinks()
    cleanup()
    mydb.close()
    print("Done")

def downloadStreamData(region):
    print('Downloading Stream Data: ' + region)
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib.request.urlretrieve('https://bcmoe.blob.core.windows.net/assets/'+region+'.json', region + '.json');

def downloadTitleIDs():
    print('Downloading Title Ids')
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib.request.urlretrieve('https://raw.githubusercontent.com/manami-project/anime-offline-database/master/anime-offline-database.json', 'anime-offline-database.json');

def loadMALIds():
    print('Loading MyAnimeList title ids')
    with open('anime-offline-database.json') as json_file:
        titledata = json.load(json_file)
        mycursor = mydb.cursor(dictionary=True)
        sql = "SELECT titleid, title, mal_id FROM titles WHERE mal_id IS NULL;"
        mycursor.execute(sql)
        results = mycursor.fetchall()
        if len(results) > 0:
            for title in results:
                for titlerecord in titledata['data']:
                    comparetitle = title['title']
                    ntitle = titlerecord['title'];
                    match = False
                    if ntitle.upper() == comparetitle.upper():
                        match = True
                    else:
                        for synonym in titlerecord['synonyms']:
                            if synonym.upper() == comparetitle.upper():
                                match = True
                                break
                    if match:
                        for source in titlerecord['sources']:
                            if "myanimelist.net" in source:
                                tmpstr = source.replace("https://myanimelist.net/anime/", "")
                                titleidint = int(tmpstr)
                                updateAddMALID(title["titleid"], titleidint)
                                break
    print('Loading MyAnimeList title ids done')

def truncateStagingTables():
    print('Truncating staging tables')
    mycursor = mydb.cursor()
    sql = "TRUNCATE TABLE staging"
    mycursor.execute(sql)
    mydb.commit()

def loadStagingTables(region):
    print('Loading ' + region + '.json')
    with open(region + '.json') as json_file:
        data = json.load(json_file)
        for show in data['shows']:
            mycursor = mydb.cursor()
            sql = "INSERT INTO staging (title, streamsitetitle, streamsiteurl, region) VALUES (%s, %s, %s, %s)"
            for streamingsite in show["sites"].keys():
                if "http://" in show["sites"][streamingsite] or "https://" in show["sites"][streamingsite]:
                    val = [show["name"], streamingsite, show["sites"][streamingsite],region];
                    mycursor.execute(sql, val)
            mydb.commit()
        print('Finished Loading ' + region + '.json')

def loadRegions():
    print('Loading regions table')
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT DISTINCT region FROM staging;"
    mycursor.execute(sql)
    results = mycursor.fetchall()
    for result in results:
        if checkRegion(result["region"]) == True:
            continue
        else:
            insertcursor = mydb.cursor()
            sql = "INSERT INTO region (regionname) VALUES (%s)"
            val = [result["region"]]
            insertcursor.execute(sql,val)
    mydb.commit()
    print('Loading regions table done')

def checkRegion(region):
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT id, regionname FROM region WHERE regionname = %s;"
    val = [region]
    mycursor.execute(sql,val)
    results = mycursor.fetchall()
    if len(results) > 0:
        return True
    return False

def loadLinks():
    print('Loading links table')
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT * FROM staging;"
    mycursor.execute(sql)
    results = mycursor.fetchall()
    for result in results:
        titleid = lookupTitle(result["title"])
        siteid = lookupSite(result["streamsitetitle"])
        regionid = lookupRegion(result["region"])
        url = result["streamsiteurl"]
        if titleid == -1 | siteid == -1 | regionid == -1:
            continue
        else:
            if (checkLink(titleid,regionid,siteid)):
                updatelink(titleid,url,siteid,regionid)
            else:
                insertLink(titleid,url,siteid,regionid)
    print('Loading links table done')

def insertLink(titleid, url, siteid, regionid):
    insertcursor = mydb.cursor()
    sql = "INSERT INTO links (titleid, url, siteid, regionid) VALUES (%s, %s, %s, %s)"
    val = [titleid, url, siteid, regionid]
    insertcursor.execute(sql, val)
    mydb.commit()

def updatelink(titleid, url, siteid, regionid):
    updatecursor = mydb.cursor()
    sql = "UPDATE links SET url = %s WHERE titleid = %s AND siteid = %s AND regionid = %s"
    val = [url, titleid, siteid, regionid]
    updatecursor.execute(sql,val)
    mydb.commit()

def checkLink(titleid, regionid, siteid):
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT id, titleid, regionid, siteid FROM links WHERE titleid = %s AND regionid = %s AND siteid = %s;"
    val = [titleid, regionid, siteid]
    mycursor.execute(sql,val)
    results = mycursor.fetchall()
    if len(results) > 0:
        return True
    return False

def loadTitles():
    print('Loading titles table')
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT DISTINCT title FROM staging;"
    mycursor.execute(sql)
    results = mycursor.fetchall()
    for result in results:
        if checkTitle(result["title"]) == True:
            continue
        else:
            insertcursor = mydb.cursor()
            sql = "INSERT INTO titles (title) VALUES (%s)"
            val = [result["title"]]
            insertcursor.execute(sql,val)
    mydb.commit()
    print('Loading titles table done')

def updateAddMALID(id, malid):
    updatecursor = mydb.cursor()
    sql = "UPDATE titles SET mal_id = %s WHERE titleid = %s"
    val = [malid, id]
    updatecursor.execute(sql,val)
    mydb.commit()

def checkTitle(title):
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT titleid, title FROM titles WHERE title = %s;"
    val = [title]
    mycursor.execute(sql,val)
    results = mycursor.fetchall()
    if len(results) > 0:
        return True
    return False

def loadSites():
    print('Loading sites table')
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT DISTINCT streamsitetitle FROM staging;"
    mycursor.execute(sql)
    results = mycursor.fetchall()
    for result in results:
        if checkSite(result["streamsitetitle"]) == True:
            continue
        else:
            insertcursor = mydb.cursor()
            sql = "INSERT INTO sites (sitename) VALUES (%s)"
            val = [result["streamsitetitle"]]
            insertcursor.execute(sql,val)
    mydb.commit()

def checkSite(sitename):
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT id, sitename FROM sites WHERE sitename = %s;"
    val = [sitename]
    mycursor.execute(sql,val)
    results = mycursor.fetchall()
    if len(results) > 0:
        return True
    return False

def lookupTitle(title):
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT titleid, title FROM titles WHERE title = %s;"
    val = [title]
    mycursor.execute(sql,val)
    results = mycursor.fetchall()
    if len(results) > 0:
        return results[0]["titleid"]
    return -1

def lookupSite(site):
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT id, sitename FROM sites WHERE sitename = %s;"
    val = [site]
    mycursor.execute(sql,val)
    results = mycursor.fetchall()
    if len(results) > 0:
        return results[0]["id"]
    return -1

def lookupRegion(region):
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT id, regionname FROM region WHERE regionname = %s;"
    val = [region]
    mycursor.execute(sql,val)
    results = mycursor.fetchall()
    if len(results) > 0:
        return results[0]["id"]
    return -1

def cleanup():
    print('Performing cleanup')
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT l.id, t.title, s.sitename, r.regionname, l.url, t.mal_id from region AS r, links AS l, sites AS s, titles AS t WHERE l.titleid = t.titleid AND l.siteid = s.id AND l.regionid = r.id"
    mycursor.execute(sql)
    loadedresults = mycursor.fetchall()
    sql = "SELECT * FROM staging"
    mycursor.execute(sql)
    stagingresults = mycursor.fetchall()
    for loadedresult in loadedresults:
        found = False
        for stageresult in stagingresults:
            if loadedresult["url"] == stageresult["streamsiteurl"] and loadedresult["regionname"] == stageresult["region"]:
                found = True
        if not found:
            print("Stream no longer exist, deleting URL: " + loadedresult["url"])
            deleteLink(loadedresult["id"])
    print("Cleanup complete")

def deleteLink(id):
    deletecursor = mydb.cursor()
    sql = "DELETE FROM links WHERE id = %s"
    val = [id]
    deletecursor.execute(sql, val)
    mydb.commit()

if __name__== "__main__":
    main()
