# -*- coding: utf-8 -*-
"""票40 判定 SPEC 彙整(kind-04,300 張)。"""
import _speckind04_p1
import _speckind04_p2
import _speckind04_p3
import _speckind04_p4
import _speckind04_p5
import _speckind04_p6
import _speckind04_p7
import _speckind04_p8
import _speckind04_p9
import _speckind04_p10
import _speckind04_p11
import _speckind04_p12
import _speckind04_p13
import _speckind04_p14

PARTS = (_speckind04_p1, _speckind04_p2, _speckind04_p3, _speckind04_p4,
         _speckind04_p5, _speckind04_p6, _speckind04_p7, _speckind04_p8,
         _speckind04_p9, _speckind04_p10, _speckind04_p11, _speckind04_p12,
         _speckind04_p13, _speckind04_p14)


def fill(add):
    for part in PARTS:
        part(add) if callable(part) else part.part(add)
