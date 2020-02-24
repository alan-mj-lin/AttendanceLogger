#!/usr/bin/env python3
# From: https://developers.google.com/sheets/api/quickstart/python
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START sheets_quickstart]

from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import datetime
import pyinotify
import lcd_i2c
import Adafruit_BBIO.GPIO as GPIO
import time
from time import sleep
import sys
import signal
from contextlib import contextmanager
import logging
from timeout import timeout 

logging.basicConfig(filename='app.log', filemode='w', level=logging.DEBUG)
logging.warning('This will get logged to a file')

redLEDPath = '/sys/class/gpio/gpio45/value'
greenLEDPath = '/sys/class/gpio/gpio69/value'

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/spreadsheets'

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1NrjRyLdJXOv9Sv5fL32aeQTmobcZ_M9Gj3vp1jX9sgM'
RANGE_NAME = 'A2'

lessons_t2 = {1: "20", 2: "21", 3: "22", 4: "23", 5: "24", 6: "25", 7: "26", 8: "27", 9: "28", 10: "29", 11: "30",
           12: "31", 13: "32"}

names = ["Michelle", "Vivian", "Monica", "Elaine", "Na", "Leah", "Ann Qing", "Louis",
         "Nathan H.", "Amos", "Jaden", "Edward", "Leo Fang", "Jeremy", "Nathan Z.",
         "Lucas", "Austen", "Haniel"]

column = ["C", "D", "E", "F", "G", "H", "I", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V"]
row = ''

lcd_call = 0

scroll_path = "/sys/logger/gpio44/"
update_path = "/sys/logger/gpio68/"

old_switch_state = 0
name_count = 0


def turn_green_on():
    f = open(greenLEDPath, 'w+')
    f.write("1\n")
    f.close()


def turn_green_off():
    f = open(greenLEDPath, 'w+')
    f.write("0\n")
    f.close()


def turn_red_on():
    f = open(redLEDPath, 'w+')
    f.write("1\n")
    f.close()


def turn_red_off():
    f = open(redLEDPath, 'w+')
    f.write("0\n")
    f.close()


def ack_led():
    logging.debug('Ack')
    turn_green_on()
    sleep(0.2)
    turn_green_off()
    sleep(0.2)
    turn_green_on()
    sleep(0.2)
    turn_green_off()


def fail_led():
    turn_red_on()
    sleep(1)
    turn_red_off()


store = file.Storage('tokenPython.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
    creds = tools.run_flow(flow, store)
connection = False
try:
    service = build('sheets', 'v4', http=creds.authorize(Http()))
    ack_led()
except:
    print('No connection ')
    logging.warning('No connection')
    pass

while not connection:
    try:
        service = build('sheets', 'v4', http=creds.authorize(Http()))
        connection = True
        ack_led()
        logging.debug('Connected ')
    except:
        print('No connection ')
        logging.warning('No connection')
        turn_red_on()
        sleep(1)
        turn_red_off()
        sleep(1)
        pass



@contextmanager
def timeout(time):
    signal.signal(signal.SIGALRM, raise_timeout)
    signal.alarm(time)
    try:
        yield
    except TimeoutError:
        pass
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)


def raise_timeout(signum, frame):
    raise TimeoutError


def try_connect():
    global connection
    global service
    logging.debug('Trying to reconnect...')
    while not connection:
        try:
            service = build('sheets', 'v4', http=creds.authorize(Http()))
            logging.debug(service)
            connection = True
            ack_led()
            logging.debug('Connected ')
            print('Update failed')
            logging.debug('Update failed..')
            fail_led()
        except:
            print('No connection..')
            logging.warning('No connection')
            turn_red_on()
            sleep(1)
            turn_red_off()
            sleep(1)
            pass


def update_button():
    global service
    global name_count
    global RANGE_NAME
    global row
    global lcd_call
    global connection
    
    f = open(update_path + "pressTime", "r")

    button_string = f.read()
    button_time = int(button_string)

    if button_time >= 1 and row != '':
        # callback to flash LED
        if lcd_call != 0:
            try:
                correct(service)
                # value = read_cell_name(service)
                # callback for ACK LED if corrected
                # callback for fail LED if not corrected
                # print(value[0][0])
                # if value[0][0] == "0":
                ack_led()
                logging.debug('Correction made.. ')
                print("Correction made..")
                # else:
                    # fail_led()
                    # print("Correction failed.. ")
            except Exception:              
                connection = False
                logging.debug('Lost connection..')
                try_connect()
    elif button_time < 1 and row != '':
        if lcd_call !=0:
            try:
                update(service)
                #value = read_cell_name(service)
                # callback for ACK LED if updated
                # callback for fail LED if not updated
                # print(type(value[0][0]))
                # if value[0][0] == "1":
                ack_led()
                logging.debug('Update success..')
                print("Update success.. ")
                #else:
                    #fail_led()
                    #print("Update failed.. ")
            except Exception:
                connection = False
                logging.debug('Lost connection..')
                try_connect()


def app_init():
    lcd_i2c.lcd_init()
    logging.debug('initializing app ')




def leds_off():
    turn_red_off()
    turn_green_off()


def scroll_button():
    global service
    global name_count
    global RANGE_NAME
    global row
    global lcd_call

    name_string = names[name_count]
    lcd_i2c.lcd_string(name_string, lcd_i2c.LCD_LINE_1)
    lcd_call += 1
    RANGE_NAME = column[name_count] + row
    if name_count < 15:
        name_count += 1
    else:
        name_count = 0
    logging.debug('Scroll press')
    print("Button pressed ")


def update(service):
    """Shows basic usage of the Sheets API.
    Writes values to a sample spreadsheet.
    """
    with timeout(5):
        # Call the Sheets API
        # Compute a timestamp and pass the first two arguments
        logging.debug('Updating..')
        values = [[1]]
        body = {'values': values}
        result = service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID,
                                                    range=RANGE_NAME,
                                                    #  How the input data should be interpreted.
                                                    valueInputOption='USER_ENTERED',
                                                    # How the input data should be inserted.
                                                    # insertDataOption='INSERT_ROWS'
                                                    body=body
                                                    ).execute()
        print(result)
        print('done')


def correct(service):
    logging.debug('Correcting..')
    values = [[0]]
    body = {'values': values}
    result = service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID,
                                                    range=RANGE_NAME,
                                                    #  How the input data should be interpreted.
                                                    valueInputOption='USER_ENTERED',
                                                    # How the input data should be inserted.
                                                    # insertDataOption='INSERT_ROWS'
                                                    body=body
                                                    ).execute()


def read_cell_name(service):
    logging.debug('Reading name..')
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    value = result.get('values', [])
    return value

def read_cell_dates(service):
    logging.debug('Reading dates..')
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='A1:A66').execute()
    dates = result.get('values', [])
    return dates


class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CLOSE_NOWRITE(self, evt):
        if evt.pathname == '/sys/logger/gpio44/activate':
            print('Scroll pressTime was changed!')
            scroll_button()
        elif evt.pathname == update_path + 'activate':
            print('Update pressTime was changed!')
            update_button()


def main():
    global RANGE_NAME
    global row
    global name_count
    global old_switch_state

    app_init()

    # lcd_i2c.lcd_string("Hello", lcd_i2c.LCD_LINE_1)

    is_lesson = False

    time = datetime.datetime.now()
    time_read = time.strftime("%m/%d/%Y").split('/')
    for i in range(len(time_read)):
        time_read[i] = time_read[i].lstrip('0')
    time_str = time_read[0] + '/' +time_read[1] + '/' + time_read[2]
    logging.debug('The date is ' + time_str)
    date_list = read_cell_dates(service)

    for i in range(len(date_list)):
        if date_list[i]:
            if date_list[i][0] == time_str:
                row = str(i + 1)
                print(row)
                is_lesson = True
    
    print(time_str)

    if not is_lesson:
        logging.debug('No lesson today..')
        fail_led()
        print('No lesson today.. ')
    else:
        logging.debug('Lesson today - updates active')
        ack_led()
        print('Time to take roll.. ')

    eventHandler = EventHandler()
    wm = pyinotify.WatchManager()
    mask = pyinotify.IN_CLOSE_NOWRITE
    notifier = pyinotify.Notifier(wm, eventHandler)
    wdd1 = wm.add_watch(scroll_path + 'activate', mask)
    wdd2 = wm.add_watch(update_path + 'activate', mask)
    notifier.loop()


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        logging.warning('Interrupted')
        lcd_i2c.lcd_byte(0x01, lcd_i2c.LCD_CMD)
        GPIO.cleanup()
    finally:
        GPIO.cleanup()
