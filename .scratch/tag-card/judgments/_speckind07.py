# -*- coding: utf-8 -*-
"""票43 判定 SPEC 彙整(kind-07,300 張)。"""
import _speckind07_p1
import _speckind07_p2
import _speckind07_p3
import _speckind07_p4
import _speckind07_p5
import _speckind07_p6
import _speckind07_p7
import _speckind07_p8
import _speckind07_p9
import _speckind07_p10
import _speckind07_p11
import _speckind07_p12
import _speckind07_p13
import _speckind07_p14
import _speckind07_p15

PARTS = (_speckind07_p1, _speckind07_p2, _speckind07_p3, _speckind07_p4, _speckind07_p5, _speckind07_p6, _speckind07_p7, _speckind07_p8, _speckind07_p9, _speckind07_p10, _speckind07_p11, _speckind07_p12, _speckind07_p13, _speckind07_p14, _speckind07_p15)


def fill(add):
    for part in PARTS:
        part.part(add)
