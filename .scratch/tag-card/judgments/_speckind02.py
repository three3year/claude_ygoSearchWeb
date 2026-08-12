# -*- coding: utf-8 -*-
"""票38 判定 SPEC 彙整(kind-02,300 張)。"""
import _speckind02_p1
import _speckind02_p2
import _speckind02_p3
import _speckind02_p4
import _speckind02_p5
import _speckind02_p6
import _speckind02_p7
import _speckind02_p8
import _speckind02_p9
import _speckind02_p10
import _speckind02_p11
import _speckind02_p12
import _speckind02_p13
import _speckind02_p14
import _speckind02_p15
import _speckind02_p16
import _speckind02_p17

PARTS = (_speckind02_p1, _speckind02_p2, _speckind02_p3, _speckind02_p4,
         _speckind02_p5, _speckind02_p6, _speckind02_p7, _speckind02_p8,
         _speckind02_p9, _speckind02_p10, _speckind02_p11, _speckind02_p12,
         _speckind02_p13, _speckind02_p14, _speckind02_p15, _speckind02_p16,
         _speckind02_p17)


def fill(add):
    for part in PARTS:
        part.part(add)
