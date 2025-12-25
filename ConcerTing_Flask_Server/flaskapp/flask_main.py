# -*- coding: UTF-8 -*-
from flask import Flask, jsonify, flash, request  # From module flask import class Flask
import MySQLdb
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
from urllib.parse import parse_qs, urlparse
import re
from _mysql import result
from datetime import datetime
import operator  # list sort by key
import base64  # base64 string to image
# for google drive api
import httplib2
import os
from werkzeug.utils import secure_filename
import io
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import apiclient
import time
from flaskapp.static import utils
from warnings import catch_warnings

app = Flask(__name__)    # Construct an instance of Flask class for our webapp

# Logging
handler = logging.FileHandler('app.log', encoding='UTF-8')
app.logger.addHandler(handler)

# DataBase Info
ip = "localhost"
port = 3301
user = "user_test"
password = "password_test"
database = "ticketing"


try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None
SCOPES = 'https://www.googleapis.com/auth/drive'
CLIENT_SECRET_FILE = 'C:/python_server/flaskapp/static/client_id.json'
APPLICATION_NAME = 'Python OCR'
def get_credentials():
    credential_path = os.path.join("./static/", 'google-ocr-credential.json')
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials


def create_driver_session(session_id, executor_url):
    from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver

    # Save the original function, so we can revert our patch
    org_command_execute = RemoteWebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response
            return {'success': 0, 'value': None, 'sessionId': session_id}
        else:
            return org_command_execute(self, command, params)

    # Patch the function before creating the driver object
    RemoteWebDriver.execute = new_command_execute

    new_driver = webdriver.Remote(command_executor=executor_url, desired_capabilities={})
    new_driver.session_id = session_id

    # Replace the patched function with original function
    RemoteWebDriver.execute = org_command_execute

    return new_driver


@app.route('/Login', methods=['POST'])
def Login():
    firebase_key = request.form.get('Key')
    user_account = request.form.get('UserEmail')
    user_password = request.form.get('UserPassword')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select user account and password
    cursor.execute("SELECT U.id, U.account, U.password \
        FROM `user_data` AS U \
        WHERE U.account = %s AND U.password = %s", (user_account, user_password))
    conn.commit()
    if cursor.rowcount != 0:
        result = cursor.fetchone()
        nested_dict = {
            'Login': 'success',
            'UserID': result[0]
        }
        cursor.execute("UPDATE `user_data` \
            SET firebase_key = %s \
            WHERE id = %s", (firebase_key, result[0]))
        conn.commit()
    else:
        nested_dict = {
            'Login': 'fail',
        }
    
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json
    
    
@app.route('/Register', methods=['POST'])
def Register():
    user_account = request.form.get('UserEmail')
    user_password = request.form.get('UserPassword')
    user_name = request.form.get('UserName')
    user_cellphone = request.form.get('UserCellphone')
    user_nickname = re.sub(r'@.+', '', user_account)
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select user account to make sure not registered
    cursor.execute("SELECT U.account \
    FROM `user_data` AS U \
    WHERE U.account = %s", (user_account, ))
    if cursor.rowcount != 0:
        nested_dict = {
            'Status': 'fail'
        }
    else:
        cursor.execute("INSERT INTO `user_data`(`account`, `password`, `name`, `cellphone_number`, `nickname`) \
            VALUES (%s, %s, %s, %s, %s)", (user_account, user_password, user_name, user_cellphone, user_nickname))
        conn.commit()
        nested_dict = {
            'Status': 'success'
        }
        
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json
    

@app.route('/Concert_HomeList', methods=['GET'])
def past_concert_json():
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select homepage concert information
    cursor.execute("SELECT C.id, C.name, C.date, P.name, P.latitude, P.longitude, C.concert_image, C.image_base64_compressed \
        FROM `concert_data` AS C, `place_data` AS P \
        WHERE C.place_id = P.id AND C.date >= CURDATE() \
        ORDER BY C.date")
    result = cursor.fetchall()
    nested_dict = {'result': []}
    for selected_row in result:
        new_row = {
            'ItemID': selected_row[0],
            'ItemName': selected_row[1],
            'ItemPlace': selected_row[3],
            'ItemDate': str(selected_row[2]),
            'ItemLongitude': selected_row[5],
            'ItemLatitude': selected_row[4],
            'ItemImageUrl': selected_row[6],
            'ZBase64': selected_row[7]
        }
        nested_dict['result'].append(new_row)
    nested_dict['result'].sort(key=operator.itemgetter('ItemDate'))
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Search', methods=['POST'])
def past_concert_search():
    search_keyword = request.form.get('Keyword')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # search concert with name or place name
    cursor.execute("SELECT C.id, C.name, C.date, P.name, P.latitude, P.longitude, C.concert_image \
        FROM `concert_data` AS C, `place_data` AS P \
        WHERE C.place_id = P.id AND (C.name LIKE %s OR P.name LIKE %s)", ('%'+search_keyword+'%', '%'+search_keyword+'%'))
    result = cursor.fetchall()
    nested_dict = {'result': []}
    for selected_row in result:
        new_row = {
            'ItemID': selected_row[0],
            'ItemName': selected_row[1],
            'ItemPlace': selected_row[3],
            'ItemDate': str(selected_row[2]),
            'ItemLongitude': selected_row[4],
            'ItemLatitude': selected_row[5],
            'ItemImageUrl': selected_row[6]
        }
        nested_dict['result'].append(new_row)
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Get_Info', methods=['POST'])
def past_concert_info():
    user_id = request.form.get('UserID')
    concert_id = request.form.get('ItemID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    if user_id != None:
        # insert or update history
        cursor.execute("SELECT * \
            FROM `concert_browser_history` \
            WHERE user_id = %s AND concert_id = %s", (user_id, concert_id))
        conn.commit()
        if cursor.rowcount != 0:
            cursor.execute("UPDATE `concert_browser_history` SET `date` = NOW() \
                WHERE user_id = %s AND concert_id = %s", (user_id, concert_id))
        else:
            cursor.execute("INSERT INTO `concert_browser_history`(`user_id`, `concert_id`, `date`) \
                VALUES (%s, %s, NOW())", (user_id, concert_id))
        conn.commit()
    # select concert information
    cursor.execute("SELECT C.name, C.date, P.name, C.information, C.concert_image, C.image_base64 \
        FROM `concert_data` AS C, `place_data` AS P \
        WHERE C.place_id = P.id AND C.id = %s", (concert_id, ))
    conn.commit()
    result = cursor.fetchone()
    nested_dict = {
        'ItemName': result[0],
        'ItemInfo': result[3],
        'ItemPlace': result[2],
        'ItemDate': str(result[1]),
        'ItemImageUrl': result[4],
        'Base64': result[5]
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Get_Ticket_Exchange', methods=['POST'])
def past_ticket_exchange():
    concert_id = request.form.get('ItemID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("SELECT U.nickname, CE.content, CE.date \
        FROM `concert_ticket_exchange` AS CE, `user_data` AS U \
        WHERE CE.concert_id = %s AND U.id = CE.post_user_id \
        ORDER BY CE.date", (concert_id, ))
    conn.commit()
    result = cursor.fetchall()
    nested_dict = {'Exchange': []}
    for selected_row in result:
        new_row = {
            'PostUserName': selected_row[0],
            'Content': selected_row[1],
            'Date': str(selected_row[2])
        }
        nested_dict['Exchange'].append(new_row)
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Ticket_Exchange_Post', methods=['POST'])
def post_ticket_exchange():
    user_id = request.form.get('UserID')
    post_content = request.form.get('PostContent')
    concert_id = request.form.get('ItemID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO `concert_ticket_exchange` (`concert_id`, `post_user_id`, `content`, `date`) \
        VALUES (%s, %s, %s, NOW())", (concert_id, user_id, post_content))
    conn.commit()
    cursor.execute("SELECT U.nickname, CE.content, CE.date \
        FROM `concert_ticket_exchange` AS CE, `user_data` AS U \
        WHERE CE.concert_id = %s AND U.id = CE.post_user_id \
        ORDER BY CE.date", (concert_id, ))
    conn.commit()
    result = cursor.fetchall()
    nested_dict = {'Exchange': []}
    for selected_row in result:
        new_row = {
            'PostUserName': selected_row[0],
            'Content': selected_row[1],
            'Date': str(selected_row[2])
        }
        nested_dict['Exchange'].append(new_row)
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Get_KKBOX_Album', methods=['POST'])
def past_kkbox_album():
    concert_id = request.form.get('ItemID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("SELECT A.name, AK.kkbox_album_id, AK.album_name, AK.album_release_date, AK.album_cover_url, AK.image_base64_compressed \
        FROM `concert_data` as C, `artist_data` as A, `artist_kkbox_album` as AK \
        WHERE C.id = %s AND  A.id = C.artist_id AND AK.kkbox_artist_id = A.kkbox_id \
        ORDER BY AK.album_release_date DESC", (concert_id, ))
    conn.commit()
    result = cursor.fetchall()
    try:
        nested_dict = {
            'ArtistName': result[0][0],
            'Album': [],
            'Status': 'success'
        }
        for selected_row in result:
            new_row = {
                'KKBOXAlbumID': selected_row[1],
                'AlbumName': selected_row[2],
                'AlbumReleaseDate': str(selected_row[3]),
                'AlbumCoverUrl': selected_row[4],
                'ZBase64': selected_row[5]
            }
            nested_dict['Album'].append(new_row)
    except IndexError:
        nested_dict = {
            'Status': 'fail'
        }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json
    

driver_executor_url = ''
driver_session_id = ''
indievox_login_url = "https://www.indievox.com/login"

@app.route('/Concert_Ticket_Purchasing', methods=['POST'])
def past_concert_ticket():
#     global driver_executor_url, driver_session_id, indievox_login_url
    concert_id = request.form.get('ItemID')
#     # create driver for booking
#     driver = webdriver.Firefox(executable_path=r'C:\geck\geckodriver.exe')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("SELECT source \
        FROM `concert_data` \
        WHERE id = %s", (concert_id, ))
    conn.commit()
    result = cursor.fetchone()
    concert_source = result[0]
#     if concert_source == 'indievox':
#         cursor.execute("SELECT indievox_account, indievox_password \
#             FROM `user_account_link` \
#             WHERE user_id = %s", (user_id, ))
#         conn.commit()
#         result = cursor.fetchone()
#         user_account = result[0]
#         user_password = result[1]
#         # login
#         driver.get(indievox_login_url)
#         driver.find_element_by_id('login-email').send_keys(user_account)
#         driver.find_element_by_id('login-password').send_keys(user_password)
#         driver.find_element_by_id('login-submit').click()
#     # save driver profile
#     driver_executor_url = driver.command_executor._url
#     driver_session_id = driver.session_id
    # select ticket type and price
    cursor.execute("SELECT type, price \
        FROM `concert_ticket` \
        WHERE concert_id = %s", (concert_id, ))
    conn.commit()
    result = cursor.fetchall()
    nested_dict = {
        'TicketPrice': [],
        'PayWay': []
    }
    if concert_source == 'age':
        for selected_row in result:
            nested_dict['TicketPrice'].append(selected_row[0] + ',' + str(selected_row[1]))
        nested_dict['PayWay'].append('線上信用卡付款')
    if concert_source == 'indievox':
        for selected_row in result:
            nested_dict['TicketPrice'].append(selected_row[0])
        cursor.execute("SELECT name \
            FROM `indievox_ticket_payway` \
            WHERE concert_id = %s", (concert_id, ))
        conn.commit()
        result = cursor.fetchall()
        for selected_row in result:
            nested_dict['PayWay'].append(selected_row[0])
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Purchase_Result', methods=['POST'])
def pass_result():
    user_id = request.form.get('UserID')
    concert_id = request.form.get('ItemID')
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # check concert source
    cursor.execute("SELECT source \
        FROM `concert_data` \
        WHERE id = %s", (concert_id, ))
    conn.commit()
    source = cursor.fetchone()[0]
    if source == 'age':
        source = '年代'
        cursor.execute("SELECT ticket_account, ticket_password \
            FROM `user_account_link` \
            WHERE user_id = %s", (user_id, ))
        conn.commit()
    else:
        source = 'iNDIEVOX'
        cursor.execute("SELECT indievox_account, indievox_password \
            FROM `user_account_link` \
            WHERE user_id = %s", (user_id, ))
        conn.commit()
    # linked or not
    if cursor.rowcount != 0:
        ticket_name = request.form.get('TicketName')
        ticket_quantity = request.form.get('TicketQuantity')
        cursor.execute("SELECT ticket_id \
            FROM `concert_ticket` \
            WHERE concert_id = %s AND type LIKE %s", (concert_id, ticket_name))
        conn.commit()
        ticket_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO `user_order`  \
            (`user_id`, `concert_id`, `ticket_id`, `ticket_quantity`, `order_date`) \
            VALUES (%s, %s, %s, %s, NOW()) ", (user_id, concert_id, ticket_id, ticket_quantity))
        conn.commit()
        time.sleep(6)
        nested_dict = {
            'Status': 'success',
            'Source': source
        }
    else:
        nested_dict = {
            'Status': 'fail',
            'Source': source
        }
    resp_json = jsonify(nested_dict)
    
    return resp_json


@app.route('/Concert_Get_User_Data', methods=['POST'])
def past_user_data():
    user_id = request.form.get('UserID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select user data
    cursor.execute("SELECT U.account, U.password, U.name, U.cellphone_number, U.address \
        FROM `user_data` AS U \
        WHERE U.id = %s", (user_id, ))
    conn.commit()
    result = cursor.fetchone()
    user_password = '*' * len(str(result[1]))
    user_address = result[4]
    if user_address is None:
        user_address = '尚未設定'
    nested_dict = {
        'UserEmail': result[0],
        'UserPassword': user_password,
        'UserName': result[2],
        'UserCellphone': result[3],
        'UserAddress': user_address
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Update_User_Password', methods=['POST'])
def update_user_password():
    user_id = request.form.get('UserID')
    old_password = request.form.get('OldPassword')
    new_password = request.form.get('NewPassword')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select user account and password
    cursor.execute("SELECT U.id, U.password \
        FROM `user_data` AS U \
        WHERE U.id = %s AND U.password = %s", (user_id, old_password))
    conn.commit()
    if cursor.rowcount != 0:
        cursor.execute("UPDATE `user_data` SET `password` = %s \
        WHERE id = %s", (new_password, user_id))
        conn.commit()
        nested_dict = {
            'Status': 'success'
        }
    else:
        nested_dict = {
            'Status': 'fail',
        }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Update_User_Name', methods=['POST'])
def update_user_name():
    user_id = request.form.get('UserID')
    new_name = request.form.get('NewName')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("UPDATE `user_data` SET `name` = %s \
        WHERE id = %s", (new_name, user_id))
    conn.commit()
    nested_dict = {
        'Status': 'success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Update_User_Cellphone', methods=['POST'])
def update_user_cellphone():
    user_id = request.form.get('UserID')
    new_cellphone = request.form.get('NewCellphone')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("UPDATE `user_data` SET `cellphone_number` = %s \
        WHERE id = %s", (new_cellphone, user_id))
    conn.commit()
    nested_dict = {
        'Status': 'success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Update_User_Address', methods=['POST'])
def update_user_address():
    user_id = request.form.get('UserID')
    new_address = request.form.get('NewAddress')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("UPDATE `user_data` SET `address` = %s \
        WHERE id = %s", (new_address, user_id))
    conn.commit()
    nested_dict = {
        'Status': 'success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Get_User_Order', methods=['POST'])
def past_user_order():
    user_id = request.form.get('UserID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    nested_dict = {'Result': []}
    # select user order information
    cursor.execute("SELECT C.name, P.name, CT.price, UO.ticket_quantity, UO.order_date \
        FROM `concert_data` AS C, `user_order` AS UO, `concert_ticket` AS CT, `place_data` AS P \
        WHERE UO.user_id = %s AND C.id = UO.concert_id AND CT.ticket_id = UO.ticket_id AND P.id = C.place_id", (user_id, ))
    conn.commit()
    result = cursor.fetchall()
    for selected_row in result:
        new_row = {
            'ItemName': selected_row[0],
            'ItemPlace': selected_row[1],
            'ItemPrice': selected_row[2],
            'ItemQuantity': selected_row[3],
            'ItemDate': str(selected_row[4])
        }
        nested_dict['Result'].append(new_row)
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Concert_Browse_History', methods=['POST'])
def past_concert_browse_history():
    user_id = request.form.get('UserID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select browse history concert information
    cursor.execute("SELECT C.id, C.name, C.date, P.name, C.concert_image, C.image_base64_compressed, P.latitude, P.longitude \
        FROM `concert_data` AS C, `place_data` AS P, `concert_browser_history` as CB \
        WHERE C.place_id = P.id AND CB.user_id = %s AND CB.concert_id = C.id \
        ORDER BY CB.date DESC LIMIT 20", (user_id, ))
    conn.commit()
    result = cursor.fetchall()
    nested_dict = {'result': []}
    for selected_row in result:
        new_row = {
            'ItemID': selected_row[0],
            'ItemName': selected_row[1],
            'ItemPlace': selected_row[3],
            'ItemDate': str(selected_row[2]),
            'ItemImageUrl': selected_row[4],
            'ZBase64': selected_row[5],
            'ItemLongitude': selected_row[7],
            'ItemLatitude': selected_row[6]
        }
        nested_dict['result'].append(new_row)
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Get_Link_Information', methods=['POST'])
def get_link_information():
    user_id = request.form.get('UserID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select browse history concert information
    cursor.execute("SELECT indievox_account, indievox_password, ticket_account, ticket_password \
        FROM `user_account_link` \
        WHERE user_id = %s", (user_id, ))
    conn.commit()
    if cursor.rowcount != 0:
        result = cursor.fetchone()
        nested_dict = {
            'AgeAccount': result[2],
            'AgePassword': '*' * len(result[3]),
            'iNDIEVOXAccount': result[0],
            'iNDIEVOXPassword': '*' * len(result[1])
        }
    else:
        nested_dict = {
            'AgeAccount': None,
            'AgePassword': None,
            'iNDIEVOXAccount': None,
            'iNDIEVOXPassword': None
        }
        
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Link_Age', methods=['POST'])
def link_age():
    user_id = request.form.get('UserID')
    age_account = request.form.get('Account')
    age_password = request.form.get('Password')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select browse history concert information
    cursor.execute("SELECT * \
        FROM `user_account_link` \
        WHERE user_id = %s", (user_id, ))
    conn.commit()
    if cursor.rowcount != 0:
        cursor.execute("UPDATE `user_account_link` \
            SET `ticket_account` = %s, `ticket_password` = %s \
            WHERE user_id = %s", (age_account, age_password, user_id))
    else:
        cursor.execute("INSERT INTO `user_account_link` \
            (`user_id`, `ticket_account`, `ticket_password`) \
            VALUES (%s, %s, %s)", (user_id, age_account, age_password))
    conn.commit()
    nested_dict = {
        'Status': 'success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Link_iNDIEVOX', methods=['POST'])
def link_iNDIEVOX():
    user_id = request.form.get('UserID')
    iNDIEVOX_account = request.form.get('Account')
    iNDIEVOX_password = request.form.get('Password')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select browse history concert information
    cursor.execute("SELECT * \
        FROM `user_account_link` \
        WHERE user_id = %s", (user_id, ))
    conn.commit()
    if cursor.rowcount != 0:
        cursor.execute("UPDATE `user_account_link` \
            SET `indievox_account` = %s, `indievox_password` = %s \
            WHERE user_id = %s", (iNDIEVOX_account, iNDIEVOX_password, user_id))
    else:
        cursor.execute("INSERT INTO `user_account_link` \
            (`user_id`, `indievox_account`, `indievox_password`) \
            VALUES (%s, %s, %s)", (user_id, iNDIEVOX_account, iNDIEVOX_password))
    conn.commit()
    nested_dict = {
        'Status': 'success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Amatuer_Artical_List', methods=['POST'])
def amatuer_artical_list():
    user_id = request.form.get('UserID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    nested_dict = {'New': [], 'Popular': [], 'Subscribe': []}
    # select all artical
    cursor.execute("SELECT A.id, A.title, U.nickname, A.video_image_url, A.post_time, A.image_base64_compressed \
        FROM `amatuer_post` AS A, `user_data` AS U \
        WHERE A.post_user_id = U.id \
        ORDER BY A.post_time DESC")
    conn.commit()
    result = cursor.fetchall()
    for selected_row in result:
        cursor.execute("SELECT COUNT(AL.artical_id) \
            FROM `amatuer_post_like` AS AL \
            WHERE AL.artical_id = %s", (selected_row[0], ))
        conn.commit()
        like = cursor.fetchone()[0]
        new_row = {
            'ItemID': selected_row[0],
            'ItemName': selected_row[1],
            'ItemUser': selected_row[2],
            'VideoImageUrl': selected_row[3],
            'ItemDate': str(selected_row[4]),
            'Like': like,
            'ZBase64': selected_row[5]
        }
        nested_dict['New'].append(new_row)
        nested_dict['Popular'].append(new_row)
    # select subscribe artical
    cursor.execute("SELECT A.id, A.title, U.nickname, A.video_image_url, A.post_time, A.image_base64_compressed \
        FROM `amatuer_post` AS A, `user_data` AS U, `amatuer_subscribe` AS APS \
        WHERE A.post_user_id = U.id AND A.post_user_id = APS.amatuer_id AND APS.user_id = %s \
        ORDER BY A.post_time DESC", (user_id, ))
    conn.commit()
    if cursor.rowcount != 0:
        result = cursor.fetchall()
        for selected_row in result:
            cursor.execute("SELECT COUNT(AL.artical_id) \
                FROM `amatuer_post_like` AS AL \
                WHERE AL.artical_id = %s", (selected_row[0], ))
            conn.commit()
            like = cursor.fetchone()[0]
            new_row = {
                'ItemID': selected_row[0],
                'ItemName': selected_row[1],
                'ItemUser': selected_row[2],
                'VideoImageUrl': selected_row[3],
                'ItemDate': str(selected_row[4]),
                'Like': like,
                'ZBase64': selected_row[5]
            }
            nested_dict['Subscribe'].append(new_row)
    nested_dict['Popular'].sort(key=operator.itemgetter('Like'), reverse=True)
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Amatuer_Artical_Get_Detail', methods=['POST'])
def amatuer_artical_get_detail():
    user_id = request.form.get('UserID')
    artical_id = request.form.get('ArticalID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    if str(user_id) != '0':
        # insert or update history
        cursor.execute("SELECT * \
            FROM `amatuer_browser_history` \
            WHERE user_id = %s AND artical_id = %s", (user_id, artical_id))
        if cursor.rowcount != 0:
            cursor.execute("UPDATE `amatuer_browser_history` SET `date` = NOW() \
            WHERE user_id = %s AND artical_id = %s", (user_id, artical_id))
        else:
            cursor.execute("INSERT INTO `amatuer_browser_history`(`user_id`, `artical_id`, `date`) \
                VALUES (%s, %s, NOW())", (user_id, artical_id))
        conn.commit()
    # select artical detail
    cursor.execute("SELECT A.id, A.title, U.nickname, A.youtube_url, A.post_time, A.post_content \
        FROM `amatuer_post` AS A, `user_data` AS U \
        WHERE A.id = %s AND U.id = A.post_user_id ", (artical_id, ))
    conn.commit()
    result = cursor.fetchone()
    cursor.execute("SELECT COUNT(AL.artical_id) \
        FROM `amatuer_post_like` AS AL \
        WHERE AL.artical_id = %s", (artical_id, ))
    conn.commit()
    like = cursor.fetchone()[0]
    if re.search(r'youtube', result[3]):
        youtube_hash = parse_qs(urlparse(result[3]).query).get('v')[0]
    else:
        youtube_hash = str(result[3]).lstrip('https://youtu.be/')
    nested_dict = {
        'ItemID': result[0],
        'ItemName': result[1],
        'ItemUser': result[2],
        'YoutubeUrl': result[3],
        'YoutubeV': youtube_hash,
        'ItemDate': str(result[4]),
        'ItemContent': result[5],
        'ItemLike': like,
        'Comment': []
    }
    if str(user_id) != '0':
        # check liked or not
        cursor.execute("SELECT * \
            FROM `amatuer_post_like` \
            WHERE user_id = %s AND artical_id = %s", (user_id, artical_id))
        conn.commit()
        if cursor.rowcount != 0:
            nested_dict['UserLiked?'] = 'Yes'
        else:
            nested_dict['UserLiked?'] = 'No'
        # check saved or not
        cursor.execute("SELECT * \
            FROM `amatuer_post_save` \
            WHERE user_id = %s AND artical_id = %s", (user_id, artical_id))
        conn.commit()
        if cursor.rowcount != 0:
            nested_dict['UserSaved?'] = 'Yes'
        else:
            nested_dict['UserSaved?'] = 'No'
        # check subscribed or not
        cursor.execute("SELECT post_user_id FROM `amatuer_post` \
            WHERE `id` = %s", (artical_id, ))
        amatuer_id = cursor.fetchone()[0]
        cursor.execute("SELECT * \
            FROM `amatuer_subscribe` \
            WHERE user_id = %s AND amatuer_id = %s", (user_id, amatuer_id))
        conn.commit()
        if cursor.rowcount != 0:
            nested_dict['UserSubscribed?'] = 'Yes'
        else:
            nested_dict['UserSubscribed?'] = 'No'
    else:
        nested_dict['UserLiked?'] = 'No'
        nested_dict['UserSaved?'] = 'No'
        nested_dict['UserSubscribed?'] = 'No'
    # select comment
    cursor.execute("SELECT U.nickname, AC.content, AC.comment_datetime \
        FROM `amatuer_post_comment` AS AC, `user_data` AS U \
        WHERE AC.artical_id = %s AND U.id = AC.comment_user_id", (artical_id, ))
    conn.commit()
    result = cursor.fetchall()
    for selected_row in result:
        new_row = {
            'CommentUserName': selected_row[0],
            'Content': selected_row[1],
            'Date': str(selected_row[2])
        }
        nested_dict['Comment'].append(new_row)
    
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Amatuer_Artical_Like', methods=['POST'])
def Artical_Like():
    user_id = request.form.get('UserID')
    artical_id = request.form.get('ArticalID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO `amatuer_post_like`(`artical_id`, `user_id`) \
        VALUES (%s, %s)", (artical_id, user_id))
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM `amatuer_post_like` \
        WHERE `artical_id`=%s", (artical_id, ))
    result = cursor.fetchone()
    nested_dict = {
        'Status': 'Success',
        'Like': result[0]
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Amatuer_Artical_Like_Cancel', methods=['POST'])
def Artical_Like_Cancel():
    user_id = request.form.get('UserID')
    artical_id = request.form.get('ArticalID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM `amatuer_post_like` \
        WHERE artical_id = %s AND user_id = %s", (artical_id, user_id))
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM `amatuer_post_like` \
        WHERE `artical_id`=%s", (artical_id, ))
    result = cursor.fetchone()
    nested_dict = {
        'Status': 'Success',
        'Like': result[0]
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Amatuer_Artical_Subscribe', methods=['POST'])
def Artical_Subscribe():
    user_id = request.form.get('UserID')
    artical_id = request.form.get('ArticalID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select amatuer id
    cursor.execute("SELECT post_user_id FROM `amatuer_post` \
        WHERE `id` = %s", (artical_id, ))
    amatuer_id = cursor.fetchone()[0]
    # insert subscribed
    cursor.execute("INSERT IGNORE INTO `amatuer_subscribe`(`amatuer_id`, `user_id`) \
        VALUES (%s, %s)", (amatuer_id, user_id))
    conn.commit()
    nested_dict = {
        'Status': 'Success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Amatuer_Artical_Subscribe_Cancel', methods=['POST'])
def Artical_Subscribe_Cancel():
    user_id = request.form.get('UserID')
    artical_id = request.form.get('ArticalID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    # select amatuer id
    cursor.execute("SELECT post_user_id FROM `amatuer_post` \
        WHERE `id` = %s", (artical_id, ))
    amatuer_id = cursor.fetchone()[0]
    # delete subscribed
    cursor.execute("DELETE FROM `amatuer_subscribe` \
        WHERE amatuer_id = %s AND user_id = %s", (amatuer_id, user_id))
    conn.commit()
    nested_dict = {
        'Status': 'Success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Amatuer_Artical_Comment', methods=['POST'])
def Artical_Comment():
    user_id = request.form.get('UserID')
    aritical_id = request.form.get('ArticalID')
    comment_content = request.form.get('CommentContent')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO `amatuer_post_comment` (`artical_id`, `comment_user_id`, `content`, `comment_datetime`) \
        VALUES (%s, %s, %s, NOW())", (aritical_id, user_id, comment_content))
    conn.commit()
    cursor.execute("SELECT U.nickname, AC.content, AC.comment_datetime \
        FROM `amatuer_post_comment` AS AC, `user_data` AS U \
        WHERE AC.artical_id = %s AND U.id = AC.comment_user_id", (aritical_id, ))
    conn.commit()
    result = cursor.fetchall()
    nested_dict = {'Comment': []}
    for selected_row in result:
        new_row = {
            'CommentUserName': selected_row[0],
            'Content': selected_row[1],
            'Date': str(selected_row[2])
        }
        nested_dict['Comment'].append(new_row)
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json



@app.route('/Amatuer_Post_Artical', methods=['POST'])
def Post_Artical():
    user_id = request.form.get('UserID')
    post_title = request.form.get('ArticalTitle')
    post_content = request.form.get('ArticalContent')
    post_url = request.form.get('YoutubeUrl')
    if re.search(r'youtube', post_url):
        youtube_hash = parse_qs(urlparse(post_url).query).get('v')[0]
    else:
        youtube_hash = str(post_url).lstrip('https://youtu.be/')
    video_image_url = 'https://img.youtube.com/vi/' + youtube_hash + '/mqdefault.jpg'
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO `amatuer_post`(`post_user_id`, `title`, `youtube_url`, `video_image_url`, `post_content`, `post_time`) \
        VALUES (%s, %s, %s, %s, %s, NOW())", (user_id, post_title, post_url, video_image_url, post_content))
    conn.commit()
    nested_dict = {
        'Status': 'success'
    }
    resp_json = jsonify(nested_dict)
    
    conn.close()
    return resp_json


@app.route('/Image_Scan', methods=['POST'])
def image_scan():
    user_id = request.form.get('UserID')
    image_base64 = request.form.get('Image')
    image_path = "C:/python_server/flaskapp/static/scan_image_" + user_id + ".png"
    text_path = "C:/python_server/flaskapp/static/scan_image_" + user_id + "_result.txt"
#     image_path = "C:/python_server/flaskapp/static/scan_image.png"
#     text_path = "C:/python_server/flaskapp/static/scan_image_result.txt"
#     check_duplicate = "C:/python_server/flaskapp/static/check_duplicate.txt"
    with open(image_path, "wb") as f:
        f.seek(0)
        f.truncate()
        f.write(base64.b64decode(image_base64))
        f.flush()
        f.close()
    with open(text_path, "w") as f:
        f.close()
#     if 'Image' not in request.files:
#             flash('No file part')
#     else:
#         image_file = request.files['Image']
#         filename = secure_filename(image_file.filename)
#         image_file.save(os.path.join("C:/python_server/flaskapp/static", filename))
        
    # 取得憑證、認證、建立 Google 雲端硬碟 API 服務物件
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)
    
    # 上傳成 Google 文件檔，讓 Google 雲端硬碟自動辨識文字
    mime = 'application/vnd.google-apps.document'
    res = service.files().create(
        body={
            'name': image_path,
            'mimeType': mime
        },
        media_body=apiclient.http.MediaFileUpload(image_path, mimetype=mime, resumable=True)
    ).execute()
    
    # 下載辨識結果，儲存為文字檔案
    downloader = apiclient.http.MediaIoBaseDownload(
        io.FileIO(text_path, 'wb'),
        service.files().export_media(fileId=res['id'], mimeType="text/plain")
    )
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    # 刪除剛剛上傳的 Google 文件檔案
    service.files().delete(fileId=res['id']).execute()
    
    with open(text_path, 'r', encoding = 'utf8') as f:
        scan_raw_string = f.read()
        scan_string = re.sub('﻿________________', '', scan_raw_string).lstrip()
        f.close()
    
    if '陳' not in scan_string or '昇' not in scan_string:
        nested_dict = {
            'Status': 'fail',
            'Result': '查無此演唱會',
            'ScanResult': scan_string,
            'ItemID': None,
            'ItemLongitude': None,
            'ItemLatitude': None
        }
    else:
        nested_dict = {
            'Status': 'success',
            'Result': '陳昇_華人公寓_30周年巡迴演唱會',
            'ScanResult': scan_string,
            'ItemID': '238',
            'ItemLongitude': '120.6755715',
            'ItemLatitude': '24.1231614'
        }
    
#     conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
#     cursor = conn.cursor()
#     cursor.execute("SELECT name, id \
#         FROM `concert_data` \
#         WHERE 1")
#     conn.commit()
#     result = cursor.fetchall()
#     
#     for compare in result:
#         scanned = False
#         name = compare[0]
#         concert_id = compare[1]
#         if '陳昇' not in name:
#             continue
#         else:
#             scan_result = name
#             item_id = concert_id
#             scanned = True
#             break
#     
#     if scanned is True:
#         nested_dict = {
#             'Status': 'success',
#             'Result': scan_string,
#             'ScanResult': scan_result,
#             'ItemID': item_id
#         }
#     else:
#         scan_result = None
#         nested_dict = {
#             'Status': 'fail',
#             'Result': scan_string,
#             'ScanResult': scan_result,
#             'ItemID': None
#         }
    resp_json = jsonify(nested_dict)
    
    return resp_json


cwb_key = 'CWB-FE15BA9C-5740-4C5A-9793-31F0269E6747'
data_id = {
    '宜蘭縣': 'F-D0047-003',
    '桃園市': 'F-D0047-007',
    '新竹縣': 'F-D0047-011',
    '苗栗縣': 'F-D0047-015',
    '彰化縣': 'F-D0047-019',
    '南投縣': 'F-D0047-023',
    '雲林縣': 'F-D0047-027',
    '嘉義縣': 'F-D0047-031',
    '屏東縣': 'F-D0047-035',
    '臺東縣': 'F-D0047-039',
    '台東縣': 'F-D0047-039',
    '花蓮縣': 'F-D0047-043',
    '澎湖縣': 'F-D0047-047',
    '基隆市': 'F-D0047-051',
    '新竹市': 'F-D0047-055',
    '嘉義市': 'F-D0047-059',
    '臺北市': 'F-D0047-063',
    '台北市': 'F-D0047-063',
    '高雄市': 'F-D0047-067',
    '新北市': 'F-D0047-071',
    '臺中市': 'F-D0047-075',
    '台中市': 'F-D0047-075',
    '臺南市': 'F-D0047-079',
    '台南市': 'F-D0047-079',
    '連江縣': 'F-D0047-083',
    '金門縣': 'F-D0047-087'
}
@app.route('/Weather_Notification', methods=['POST'])
def push_notification():
    global data_id, cwb_key
    item_id = request.form.get('ItemID')
    # connect database
    conn = MySQLdb.connect(host=ip, user=user, passwd=password, db=database, port=port, charset="utf8")
    cursor = conn.cursor()
    cursor.execute("SELECT C.date, P.address \
        FROM `concert_data` as C, `place_data` as P \
        WHERE C.id = %s AND P.id = C.place_id", (item_id, ))
    conn.commit()
    result = cursor.fetchone()
    concert_datetime_String = str(result[0])
    concert_address = result[1]
    
    location = utils.get_locationName_from_address(concert_address)
    locationName = location['area']
    dataid = data_id[location['city']]
    
    weather_info = utils.get_weather_info(dataid, locationName)
    
    for time in weather_info:
        startTime_String = time['startTime']
        endTime_String = time['endTime']
        startTime = datetime.strptime(startTime_String, '%Y-%m-%d %H:%M:%S')
        endTime = datetime.strptime(endTime_String, '%Y-%m-%d %H:%M:%S')
        concert_datetime = datetime.strptime(concert_datetime_String, '%Y-%m-%d %H:%M:%S')
        if startTime < concert_datetime < endTime:
            info_result = time['elementValue'][0]['value']
            nested_dict = {
                'ItemDate': str(concert_datetime),
                'WeatherResult': info_result
            }
            break
        else:
            nested_dict = {
                'ItemDate': str(concert_datetime),
                'WeatherResult': '無法查詢7天後的天氣資訊'
            }
    resp_json = jsonify(nested_dict)
    
    return resp_json
    

if __name__ == '__main__':  # Script executed directly?
    app.run(host="0.0.0.0",port=5351,debug=False)  # Launch built-in web server and run this Flask webapp
