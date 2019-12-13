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
import lcd_i2c
import Adafruit_BBIO.GPIO as GPIO
import time
from time import sleep

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/spreadsheets'

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1Z_nyIw9YRsSfhzw1bcWjpTQoUCObXyeENp-uIwkNCtg'
RANGE_NAME = 'A2'

lessons_t2 = {1: "20", 2: "21", 3: "22", 4: "23", 5: "24", 6: "25", 7: "26", 8: "27", 9: "28", 10: "29", 11: "30",
           12: "31", 13: "32"}

names = ["Monica", "Elaine", "Na", "Leah", "Avril", "Jeremy", "Leo", "Nathan",
         "Lucas", "Austen", "Haniel", "Max", "Derrick", "Andrew", "Alan",
         "Siyuan"]

column = ["C", "D", "E", "F", "G", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V"]
row = ''

old_switch_state = 0
name_count = 0

store = file.Storage('tokenPython.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
    creds = tools.run_flow(flow, store)
service = build('sheets', 'v4', http=creds.authorize(Http()))


def button_release(channel):
    global service
    global name_count
    global RANGE_NAME
    global row

    start_time = time.time()

    while GPIO.input("P8_12") == 0:
        pass

    button_time = time.time() - start_time
    print(button_time)

    if button_time >= 2 and row != '':
        # callback to flash LED
        update(service)
    elif button_time < 2:
        name_string = names[name_count]
        lcd_i2c.lcd_string(name_string, lcd_i2c.LCD_LINE_1)
        RANGE_NAME = column[name_count] + row
        if name_count < 15:
            name_count += 1
        else:
            name_count = 0
        print("Button pressed ")


def update(service):
    """Shows basic usage of the Sheets API.
    Writes values to a sample spreadsheet.
    """

    # Call the Sheets API
    # Compute a timestamp and pass the first two arguments
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


def read_cell_dates(service):

    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='A1:A66').execute()
    dates = result.get('values', [])
    return dates


def app_init():
    GPIO.setup("P8_12", GPIO.IN)
    GPIO.add_event_detect("P8_12", GPIO.RISING, callback=button_release, bouncetime=500)

    lcd_i2c.lcd_init()

def main():
    global RANGE_NAME
    global row
    global name_count
    global old_switch_state

    app_init()
    # lcd_i2c.lcd_string("Hello", lcd_i2c.LCD_LINE_1)

    is_lesson = False

    time = datetime.datetime.now()
    time_str = time.strftime("%m/%d/%Y")

    date_list = read_cell_dates(service)

    # print(len(date_list))

    for i in range(len(date_list)):
        if date_list[i]:
            if date_list[i][0] == time_str:
                row = str(i + 1)
                # print(row)
                is_lesson = True

    if not is_lesson:
        print('No lesson today, continue or press q to quit ')
        next = input()

        if next == 'q':
            exit()
    else:
        print('Time to take roll.. ')



    while True:
        # print('Enter term number: ')
        # term = input()

        name_check = False

        # print('Enter student name: ')
        # name = input()

        """
        
        new_switch_state = GPIO.input("P8_12")

        if new_switch_state == 1 and old_switch_state == 0:
            
        old_switch_state = new_switch_state

        # if name == 'q':
            # exit()
        
        for i in range(len(names)):
            if names[i] == name:
                name_check = True
                RANGE_NAME = column[i] + row
                update(service)
        """
        # if not name_check:
            # print('No student with that name. ')


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        lcd_i2c.lcd_byte(0x01, lcd_i2c.LCD_CMD)
