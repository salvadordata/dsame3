#!/usr/bin/env python
#
# Copyright (C) 2017 Joseph W. Metcalf
#
# Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby
# granted, provided that the above copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING
# ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL,
# DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE
# USE OR PERFORMANCE OF THIS SOFTWARE.
#

# C:\Python27\python.exe dsame.py --loglevel 10 --text --source scripts\source-soundcard-multimon-ng.bat
# dsame.exe --source scripts\source-soundcard-multimon-ng.bat --loglevel 10

import sys
import defs
import argparse
import string
import logging
import datetime
import time
import subprocess

import sounddevice as sd
import soundfile as sf
import numpy as np

# Constants
SAMPLE_RATE = 44100  # Sample rate (Hz)
CHANNELS = 2        # Number of audio channels
FILE_NAME = 'recording.wav'  # Output file name

# Recording state
is_recording = 0
file = None
stream = None


# Callback function for audio input
recorded_frames = []

def callback(indata, frames, time, status):
    recorded_frames.append(indata.copy())

def set_is_recording(data):
    global is_recording
    is_recording = data


def get_is_recording():
    global is_recording
    is_recording = is_recording
    return str(is_recording)


def set_FILE_NAME(alert, path):
    global FILE_NAME
    current_dateTime = datetime.datetime.now()
    event = defs.SAME__EEE[alert]
    event = event.replace(' ', '-')
    mn = current_dateTime.strftime("%m")
    d = current_dateTime.strftime("%d")
    y = current_dateTime.strftime("%Y")
    h = current_dateTime.strftime("%I")
    m = current_dateTime.strftime("%M")
    apm = current_dateTime.strftime("%p")
    FILE_NAME = str(path[0]) + '\\' + str(mn) + '-' + str(d) + '-' + str(y) + '_' + str(h) + '-' + str(m) + '-' + str(apm) + '_' + str(
        event) + '.wav'
    # FILE_NAME = str(current_dateTime.year) + '-' + str(current_dateTime.month) + '-' + str(current_dateTime.day) + '_' + str(current_dateTime.hour) + '-' + str(current_dateTime.minute) + '_' + str(event) +'.wav'


def alert_start(JJJHHMM, format='%j%H%M'):
    import calendar
    """Convert EAS date string to datetime format"""
    utc_dt = datetime.datetime.strptime(JJJHHMM, format).replace(datetime.datetime.utcnow().year)
    timestamp = calendar.timegm(utc_dt.timetuple())
    return datetime.datetime.fromtimestamp(timestamp)


def fn_dt(dt, format='%I:%M %p'):
    """Return formated datetime"""
    return dt.strftime(format)


# ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-

def format_error(info=''):
    logging.warning(' '.join(['INVALID FORMAT', info]))


def time_str(x, type='hour'):
    if x == 1:
        return ''.join([str(x), ' ', type])
    elif x >= 2:
        return ''.join([str(x), ' ', type, 's'])


def get_length(TTTT):
    hh, mm = TTTT[:2], TTTT[2:]
    return ' '.join(filter(None, (time_str(int(hh)), time_str(int(mm), type='minute'))))


def county_decode(input, COUNTRY):
    """Convert SAME county/geographic code to text list"""
    P, SS, CCC, SSCCC = input[:1], input[1:3], input[3:], input[1:]
    if COUNTRY == 'US':
        if SSCCC in defs.SAME_CTYB:
            SAME__LOC = defs.SAME_LOCB
        else:
            SAME__LOC = defs.SAME_LOCA
        if CCC == '000':
            county = 'ALL'
        else:
            county = defs.US_SAME_CODE[SSCCC]
        return [' '.join(filter(None, (SAME__LOC[P], county))), defs.US_SAME_AREA[SS]]
    else:
        if CCC == '000':
            county = 'ALL'
        else:
            county = defs.CA_SAME_CODE[SSCCC]
        return [county, defs.CA_SAME_AREA[SS]]


def get_division(input, COUNTRY='US'):
    if COUNTRY == 'US':
        try:
            DIVISION = defs.FIPS_DIVN[input]
            if not DIVISION:
                DIVISION = 'areas'
        except:
            DIVISION = 'counties'
    else:
        DIVISION = 'areas'
    return DIVISION


def get_event(input):
    event = None
    try:
        event = defs.SAME__EEE[input]
    except:
        if input[2:] in 'WAESTMN':
            event = ' '.join(['Unknown', defs.SAME_UEEE[input[2:]]])
    return event


def get_indicator(input):
    indicator = None
    try:
        if input[2:] in 'WAESTMNR':
            indicator = input[2:]
    except:
        pass
    return indicator


def printf(output=''):
    output = output.lstrip(' ')
    output = ' '.join(output.split())
    sys.stdout.write(''.join([output, '\n']))


def alert_end(JJJHHMM, TTTT):
    alertstart = alert_start(JJJHHMM)
    delta = datetime.timedelta(hours=int(TTTT[:2]), minutes=int(TTTT[2:]))
    return alertstart + delta


def alert_length(TTTT):
    delta = datetime.timedelta(hours=int(TTTT[:2]), minutes=int(TTTT[2:]))
    return delta.seconds


def get_location(STATION=None, TYPE=None):
    location = ''
    if TYPE == 'NWS':
        try:
            location = defs.WFO_LIST[STATION]
        except:
            pass
    return location


def check_watch(watch_list, PSSCCC_list, event_list, EEE):
    if not watch_list:
        watch_list = PSSCCC_list
    if not event_list:
        event_list = [EEE]
    w, p = [], []
    w += [item[1:] for item in watch_list]
    p += [item[1:] for item in PSSCCC_list]
    if (set(w) & set(p)) and EEE in event_list:
        return True
    else:
        return False


def kwdict(**kwargs):
    return kwargs


def format_message(command, ORG='WXR', EEE='RWT', PSSCCC=[], TTTT='0030', JJJHHMM='0010000', STATION=None, TYPE=None,
                   LLLLLLLL=None, COUNTRY='US', LANG='EN', MESSAGE=None, **kwargs):
    return command.format(ORG=ORG, EEE=EEE, TTTT=TTTT, JJJHHMM=JJJHHMM, STATION=STATION, TYPE=TYPE, LLLLLLLL=LLLLLLLL,
                          COUNTRY=COUNTRY, LANG=LANG, event=get_event(EEE), type=get_indicator(EEE),
                          end=fn_dt(alert_end(JJJHHMM, TTTT)), start=fn_dt(alert_start(JJJHHMM)),
                          organization=defs.SAME__ORG[ORG]['NAME'][COUNTRY], PSSCCC='-'.join(PSSCCC),
                          location=get_location(STATION, TYPE), date=fn_dt(datetime.datetime.now(), '%c'),
                          length=get_length(TTTT), seconds=alert_length(TTTT), MESSAGE=MESSAGE, **kwargs)


def readable_message(ORG='WXR', EEE='RWT', PSSCCC=[], TTTT='0030', JJJHHMM='0010000', STATION=None, TYPE=None,
                     LLLLLLLL=None, COUNTRY='US', LANG='EN'):
    import textwrap
    printf()
    location = get_location(STATION, TYPE)
    MSG = [format_message(defs.MSG__TEXT[LANG]['MSG1'], ORG=ORG, EEE=EEE, TTTT=TTTT, JJJHHMM=JJJHHMM, STATION=STATION,
                          TYPE=TYPE, COUNTRY=COUNTRY, LANG=LANG,
                          article=defs.MSG__TEXT[LANG][defs.SAME__ORG[ORG]['ARTICLE'][COUNTRY]].title(),
                          has=defs.MSG__TEXT[LANG]['HAS'] if not defs.SAME__ORG[ORG]['PLURAL'] else
                          defs.MSG__TEXT[LANG]['HAVE'],
                          preposition=defs.MSG__TEXT[LANG]['IN'] if location != '' else '')]
    current_state = None
    for idx, item in enumerate(PSSCCC):
        county, state = county_decode(item, COUNTRY)
        if current_state != state:
            DIVISION = get_division(PSSCCC[idx][1:3], COUNTRY)
            output = defs.MSG__TEXT[LANG]['MSG2'].format(conjunction='' if idx == 0 else defs.MSG__TEXT[LANG]['AND'],
                                                         state=state, division=DIVISION)
            MSG += [''.join(output)]
            current_state = state
        MSG += [defs.MSG__TEXT[LANG]['MSG3'].format(
            county=county if county != state else defs.MSG__TEXT[LANG]['ALL'].upper(),
            punc=',' if idx != len(PSSCCC) - 1 else '.')]
    MSG += [defs.MSG__TEXT[LANG]['MSG4']]
    MSG += [''.join(['(', LLLLLLLL, ')'])]
    output = textwrap.wrap(''.join(MSG), 78)
    for item in output:
        printf(item)
    printf()
    return ''.join(MSG)


def clean_msg(same):
    valid_chars = ''.join([string.ascii_uppercase, string.digits, '+-/*'])
    same = same.upper()  # Uppercase
    msgidx = same.find('ZCZC')
    if msgidx != -1:
        same = same[msgidx:]  # Left Offset
    same = ''.join(same.split())  # Remove whitespace
    same = ''.join(filter(lambda x: x in valid_chars, same))  # Valid ASCII codes only
    slen = len(same) - 1
    if same[slen] != '-':
        ridx = same.rfind('-')
        offset = slen - ridx
        if (offset <= 8):
            same = ''.join([same.ljust(slen + (8 - offset) + 1, '?'), '-'])  # Add final dash and/or pad location field

    return same


def same_decode(same, lang, same_watch=None, event_watch=None, text=True, call=None, command=None, jsonfile=None):
    args = parse_arguments()
    global file
    global stream
    global recorded_frames
    while len(same):
        tail = same
        try:
            same = clean_msg(same)
        except:
            return
        msgidx = same.find('ZCZC')
        endidx = same.find('NNNN')
        if msgidx != -1 and (endidx == -1 or endidx > msgidx):
            # New message
            logging.debug('-' * 30)
            logging.debug(' '.join(['    Identifer found >', 'ZCZC']))
            S1, S2 = None, None
            try:
                S1, S2 = same[msgidx:].split('+', 1)
            except:
                format_error()
                return
            try:
                ZCZC, ORG, EEE, PSSCCC = S1.split('-', 3)
            except:
                format_error()
                return
            logging.debug(' '.join(['   Originator found >', ORG]))
            logging.debug(' '.join(['   Event Code found >', EEE]))
            try:
                PSSCCC_list = PSSCCC.split('-')
            except:
                format_error()

            try:
                TTTT, JJJHHMM, LLLLLLLL, tail = S2.split('-', 3)
            except:
                format_error()
                return
            logging.debug(' '.join(['   Purge Time found >', TTTT]))
            logging.debug(' '.join(['    Date Code found >', JJJHHMM]))
            logging.debug(' '.join(['Location Code found >', LLLLLLLL]))
            try:
                STATION, TYPE = LLLLLLLL.split('/')
            except ValueError:
                # Station doesn't have to have a /
                STATION = LLLLLLLL
                TYPE = None
                pass
            except:
                STATION, TYPE = None, None
                format_error()
            logging.debug(' '.join(['   SAME Codes found >', str(len(PSSCCC_list))]))
            US_bad_list = []
            CA_bad_list = []
            for code in PSSCCC_list:
                try:
                    county = defs.US_SAME_CODE[code[1:]]
                except KeyError:
                    US_bad_list.append(code)
                try:
                    county = defs.CA_SAME_CODE[code[1:]]
                except KeyError:
                    CA_bad_list.append(code)
            if len(US_bad_list) < len(CA_bad_list):
                COUNTRY = 'US'
            if len(US_bad_list) > len(CA_bad_list):
                COUNTRY = 'CA'
            if len(US_bad_list) == len(CA_bad_list):
                if type == 'CA':
                    COUNTRY = 'CA'
                else:
                    COUNTRY = 'US'
            if COUNTRY == 'CA':
                bad_list = CA_bad_list
            else:
                bad_list = US_bad_list
            logging.debug(' '.join(['Invalid Codes found >', str(len(bad_list)), ', '.join(bad_list)]))
            logging.debug(' '.join(['            Country >', COUNTRY]))
            logging.debug('-' * 30)
            for code in bad_list:
                PSSCCC_list.remove(code)
            PSSCCC_list.sort()
            if check_watch(same_watch, PSSCCC_list, event_watch, EEE):
                if text:
                    MESSAGE = readable_message(ORG, EEE, PSSCCC_list, TTTT, JJJHHMM, STATION, TYPE, LLLLLLLL, COUNTRY,
                                               lang)
                    if args.record:
                        if not is_recording:
                            # Start recording
                            sys.stdout.write('Recording started. ')
                            set_is_recording(1)
                            set_FILE_NAME(EEE, args.record)
                            sys.stdout.write(FILE_NAME)
                            sys.stdout.write('\n')
                            stream = sd.InputStream(callback=callback, channels=CHANNELS, samplerate=SAMPLE_RATE)
                            stream.start()
                else:
                    MESSAGE = None
                    if not is_recording:
                        # Start recording
                        # sys.stdout.write(str(get_is_recording()))
                        # sys.stdout.write('\n')
                        sys.stdout.write('Recording started. ')
                        set_is_recording(1)
                        set_FILE_NAME(EEE, args.record)
                        sys.stdout.write(FILE_NAME)
                        #printf(FILE_NAME)
                        sys.stdout.write('\n')
                        # sys.stdout.write(str(get_is_recording()))
                        # sys.stdout.write('\n')
                        #file = sf.SoundFile(FILE_NAME, 'w', format='WAV', samplerate=SAMPLE_RATE, channels=CHANNELS)
                        stream = sd.InputStream(callback=callback, channels=CHANNELS, samplerate=SAMPLE_RATE)
                        stream.start()
                if jsonfile:
                    try:
                        import json
                        data = kwdict(ORG=ORG, EEE=EEE, TTTT=TTTT, JJJHHMM=JJJHHMM, STATION=STATION, TYPE=TYPE,
                                      LLLLLLLL=LLLLLLLL, COUNTRY=COUNTRY, LANG=lang, event=get_event(EEE),
                                      type=get_indicator(EEE), end=fn_dt(alert_end(JJJHHMM, TTTT)),
                                      start=fn_dt(alert_start(JJJHHMM)),
                                      organization=defs.SAME__ORG[ORG]['NAME'][COUNTRY], PSSCCC=PSSCCC,
                                      PSSCCC_list=PSSCCC_list, location=get_location(STATION, TYPE),
                                      date=fn_dt(datetime.datetime.now(), '%c'), length=get_length(TTTT),
                                      seconds=alert_length(TTTT), MESSAGE=MESSAGE)
                        with open(jsonfile, 'w') as outfile:
                            json.dump(data, outfile)
                    except Exception as detail:
                        logging.error(detail)
                        return
                if command:
                    if call:
                        l_cmd = []
                        for cmd in command:
                            l_cmd.append(
                                format_message(cmd, ORG, EEE, PSSCCC_list, TTTT, JJJHHMM, STATION, TYPE, LLLLLLLL,
                                               COUNTRY, lang, MESSAGE))
                        try:
                            subprocess.call([call] + l_cmd)
                        except Exception as detail:
                            logging.error(detail)
                            return
                        pass
                    else:
                        f_cmd = format_message(' '.join(command), ORG, EEE, PSSCCC_list, TTTT, JJJHHMM, STATION, TYPE,
                                               LLLLLLLL, COUNTRY, lang, MESSAGE)
                        printf(f_cmd)
        else:
            if endidx == -1:
                logging.warning('Valid identifer not found.')
                return
            else:
                if is_recording:
                    # RECORDING STOP
                    stream.stop()
                    stream.close()
                    #file.close()
                    recorded_frames = np.concatenate(recorded_frames)
                    # sys.stdout.write(str(get_is_recording()))
                    # sys.stdout.write('\n')
                    try:
                        sf.write(FILE_NAME, recorded_frames, SAMPLE_RATE, 'PCM_24')
                        sys.stdout.write('Recording stopped. File saved as ')
                        sys.stdout.write(FILE_NAME)
                        sys.stdout.write('\n')
                        set_is_recording(0)
                    except:
                        sys.stdout.write('Error. Recording could not be saved. Please check your path and make sure it is correct and you have access. \n')
                        set_is_recording(0)
                        #return
                    # sys.stdout.write(str(get_is_recording()))
                    # sys.stdout.write('\n')
                logging.debug(' '.join(['End of Message found >', 'NNNN', str(msgidx)]))
                tail = same[msgidx:+len('NNNN')]

        # Move ahead and look for more
        same = tail


def parse_arguments():
    parser = argparse.ArgumentParser(description=defs.DESCRIPTION, prog=defs.PROGRAM, fromfile_prefix_chars='@')
    parser.add_argument('--msg', help='message to decode')
    parser.add_argument('--same', nargs='*', help='filter by SAME code')
    parser.add_argument('--event', nargs='*', help='filter by event code')
    parser.add_argument('--lang', default='EN', help='set language')
    parser.add_argument('--loglevel', default=40, type=int, choices=[10, 20, 30, 40, 50], help='set log level')
    parser.add_argument('--text', dest='text', action='store_true', help='output readable message')
    parser.add_argument('--no-text', dest='text', action='store_false', help='disable readable message')
    parser.add_argument('--version', action='version', version=' '.join([defs.PROGRAM, defs.VERSION]),
                        help='show version infomation and exit')
    parser.add_argument('--call', help='call external command')
    parser.add_argument('--command', nargs='*', help='command message')
    parser.add_argument('--json', help='write to json file')
    parser.add_argument('--source', help='source program')
    parser.add_argument('--record', nargs='*', help='Record on valid SAME tone. Set recording location. ex. "C:\\Recordings". NOTE: Paths can be either absolute or relative. ')
    parser.set_defaults(text=True)
    args, unknown = parser.parse_known_args()
    return args


def main():
    args = parse_arguments()
    logging.basicConfig(level=args.loglevel, format='%(levelname)s: %(message)s')
    if args.msg:
        same_decode(args.msg, args.lang, same_watch=args.same, event_watch=args.event, text=args.text, call=args.call,
                    command=args.command, jsonfile=args.json)
    elif args.source:
        try:
            source_process = subprocess.Popen(args.source, stdout=subprocess.PIPE)
        except Exception as detail:
            logging.error(detail)
            return
        while True:
            line = source_process.stdout.readline()

            if line:
                line1 = line.decode('ascii')
                logging.debug(line1) #ISSUE EXISTS IN THIS AREA
                same_decode(line1, args.lang, same_watch=args.same, event_watch=args.event, text=args.text,
                            call=args.call, command=args.command, jsonfile=args.json)
    else:
        while True:
            for line in sys.stdin:
                logging.debug(line)
                same_decode(line, args.lang, same_watch=args.same, event_watch=args.event, text=args.text,
                            call=args.call, command=args.command, jsonfile=args.json)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass