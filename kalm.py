#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import configparser
import time


def engage():
    # config
    parser = configparser.ConfigParser()
    with open('login') as configfile:
        parser.read_file(configfile)
    vpn_dict = parser['vpn-section']
    login = vpn_dict['login']
    password = vpn_dict['password']
    host = vpn_dict['host']

    # issue connect command
    command = "printf '" + login + "\n\n" + password + "\ny' | /opt/cisco/anyconnect/bin/vpn -s connect " + host
    os.system(command)
    # timeout while we connect
    time.sleep(30)
    return


def disengage():
    # issue disconnect command
    command = "/opt/cisco/anyconnect/bin/vpn disconnect"
    os.system(command)
    # timeout while we disconnect
    time.sleep(5)
    return