# -*- coding: utf-8 -*-
"""票42 判定 SPEC 彙整(kind-06,300 張)。"""
import _speckind06_p1
import _speckind06_p2
import _speckind06_p3
import _speckind06_p4
import _speckind06_p5
import _speckind06_p6
import _speckind06_p7
import _speckind06_p8
import _speckind06_p9
import _speckind06_p10
import _speckind06_p11
import _speckind06_p12
import _speckind06_p13
import _speckind06_p14
import _speckind06_p15
import _speckind06_p16

PARTS = (_speckind06_p1, _speckind06_p2, _speckind06_p3, _speckind06_p4, _speckind06_p5, _speckind06_p6, _speckind06_p7, _speckind06_p8, _speckind06_p9, _speckind06_p10, _speckind06_p11, _speckind06_p12, _speckind06_p13, _speckind06_p14, _speckind06_p15, _speckind06_p16)


def fill(add):
    for part in PARTS:
        part.part(add)
