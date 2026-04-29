#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from ftplib import FTP
import sqlite3
import appinfo
import io
import os
import re
from sfo.sfo import SfoFile as SfoFile
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("PS4_IP", help="PS4 ftp ip address")
parser.add_argument('--fw', default="11.00", help='currently support 5.05, 6.72, 7.02, 7.55, 9.0(?), 11.00')
parser.add_argument('--port', default="2121", help='PS4 FTP Port Number')
args = parser.parse_args()
app_db = "tmp/app.db"
PS4_IP = args.PS4_IP

port = int(args.port) if int(args.port) is not None else 2121

value_format = ""
if args.fw == "5.05":
        value_format = """("%s", "%s", "%s", "/user/appmeta/%s", "2026-04-29 02:07:47.822", "0", "0", "5", "1", "100", "0", "151", "5", "1", "gd", "0", "0", "0", "0", NULL, NULL, NULL, "%d", "2026-04-29 02:07:47.802", "0", "game", NULL, "0", "0", NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "0", NULL, NULL, NULL, NULL, NULL, "0", "0", NULL, "2026-04-29 02:07:47.757")"""
elif args.fw == "6.72":
        value_format = """("%s", "%s", "%s", "/user/appmeta/%s", "2026-04-29 02:07:47.822", "0", "0", "5", "1", "100", "0", "151", "5", "1", "gd", "0", "0", "0", "0", NULL, NULL, NULL, "%d", "2026-04-29 02:07:47.802", "0", "game", NULL, "0", "0", NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "0", NULL, NULL, NULL, NULL, NULL, "0", "0", NULL, "2026-04-29 02:07:47.757", "0", "0", "0", "0", "0", NULL)"""
elif args.fw == "10.50":
        value_format = """("%s", "%s", "%s", "/user/appmeta/%s", "2026-04-29 02:07:47.822", "0", "0", "5", "1", "100", "0", "151", "5", "1", "gd", "0", "0", "0", "0", NULL, NULL, NULL, "%d", "2026-04-29 02:07:47.802", "0", "game", NULL, "0", "0", NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "0", NULL, NULL, NULL, NULL, NULL, "0", "0", NULL, "2026-04-29 02:07:47.757", "0", "0", "0", "0", "0", NULL, "0", NULL, NULL)"""
elif args.fw == "11.00":
        value_format = """("%s", "%s", "%s", "/user/appmeta/%s", "2026-04-29 02:07:47.822", "0", "0", "5", "1", "100", "0", "151", "5", "1", "gd", "0", "0", "0", "0", NULL, NULL, NULL, "%d", "2026-04-29 02:07:47.802", "0", "game", NULL, "0", "0", NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "0", NULL, NULL, NULL, NULL, NULL, "0", "0", NULL, "2026-04-29 02:07:47.757", "0", "0", "0", "0", "0", NULL, "0", NULL, NULL, NULL)"""
else:
        raise Exception("Please provide target firmware! Currently missing --fw xx.xx parameter")

if not os.path.exists('tmp'):
        os.makedirs('tmp')

class CUSA :
        sfo = None
        size = 10000000
        is_usable = False

info = {}
files = []

def sort_files(file_to_sort) :
        if re.search("^[A-Z]", file_to_sort[-9]):
                files.append("'%s'" % file_to_sort[-9:])

def get_game_info_by_id(gameid_to_get) :
        if gameid_to_get not in info:
                info[gameid_to_get] = CUSA()

                try:
                        buffer = io.BytesIO()
                        ftp.cwd('/system_data/priv/appmeta/%s/' % gameid_to_get)
                        ftp.retrbinary("RETR param.sfo" , buffer.write)
                        buffer.seek(0)
                        sfo = SfoFile.from_reader(buffer)
                        info[gameid_to_get].sfo = sfo
                        info[gameid_to_get].size = ftp.size("/user/app/%s/app.pkg" % gameid_to_get)
                        info[gameid_to_get].is_usable = True
                except Exception as e:
                        print("Error processing %s, ignorining..." % gameid_to_get)
                        print("type error: " + str(e))

        return info[gameid_to_get]


ftp = FTP()
ftp.connect(PS4_IP, port, timeout=30)
ftp.login(user='username', passwd = 'password')
if len(files) == 0:
        ftp.cwd('/user/app/')
        ftp.dir(sort_files)
        print(files)


ftp.cwd('/system_data/priv/mms/')
lf = open(app_db, "wb")
ftp.retrbinary("RETR app.db" , lf.write)
lf.close()

conn = sqlite3.connect(app_db)

cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'tbl_appbrowse_%%';")
tables = cursor.fetchall()

files_joined = "SELECT %s AS titleid " % ' AS titleid UNION SELECT '.join(files)
tbl_appbrowse = []
for tbl in tables :
        tbl_appbrowse.append(tbl[0])
        print("Processing table: %s" % tbl[0])
        cursor.execute("SELECT T.titleid FROM (%s) T WHERE T.titleid NOT IN (SELECT titleid FROM %s);" % (files_joined, tbl[0]))
        list_id = cursor.fetchall()
        sql_list = []
        for tmp_GameID in list_id :
                GameID = tmp_GameID[0].replace("'", "")
                print(" Processing GameID: %s... " % GameID, end='')
                cusa = get_game_info_by_id(GameID)
                if cusa.is_usable == True:
                        sql_list.append(value_format
                                % (cusa.sfo['TITLE_ID'], cusa.sfo['CONTENT_ID'], cusa.sfo['TITLE'], cusa.sfo['TITLE_ID'], cusa.size))
                        print("Completed %d" % cusa.size)
                else :
                        print("Ignoring")

        if len(sql_list) > 0:
                cursor.execute("INSERT INTO %s VALUES %s;" % (tbl[0], ', '.join(sql_list)))

print('')
print('')
print('')

print("Processing table: tbl_appinfo")

cursor.execute("SELECT DISTINCT T.titleid FROM (SELECT titleid FROM %s) T WHERE T.titleid NOT IN (SELECT DISTINCT titleid FROM tbl_appinfo);" % (" UNION SELECT titleid FROM ".join(tbl_appbrowse)))
missing_appinfo_cusa_id = cursor.fetchall()
for tmp_cusa_id in missing_appinfo_cusa_id :
        current_game_id = tmp_cusa_id[0]
        print(" Processing GameID: %s... " % current_game_id, end='')
        cusa = get_game_info_by_id(current_game_id)
        if cusa.is_usable == True:
                sql_items = appinfo.get_pseudo_appinfo(cusa.sfo, cusa.size)
                for key, value in sql_items.items():
                        cursor.execute("INSERT INTO tbl_appinfo (titleid, key, val) VALUES (?, ?, ?);", [current_game_id, key, value])
                print("Completed")
        else :
                print("Skipped")

conn.commit()

conn.close()

ftp.cwd('/system_data/priv/mms/')
file = open(app_db,'rb')
ftp.storbinary('STOR app.db', file)
file.close()
