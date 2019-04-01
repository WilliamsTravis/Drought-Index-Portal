# -*- coding: utf-8 -*-
"""
Created on Sun Mar 31 15:06:05 2019

@author: User
"""


sb = "some string used for examples".encode("utf-8")
bb = base64.b64encode(sb)
bb.decode('utf-8')
bbd = base64.decodebytes(bb)
