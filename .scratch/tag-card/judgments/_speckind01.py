# -*- coding: utf-8 -*-
"""票37 判定 SPEC 彙整(kind-01,300 張)。"""
import _speckind01_p1
import _speckind01_p2
import _speckind01_p3
import _speckind01_p4
import _speckind01_p5
import _speckind01_p6
import _speckind01_p7
import _speckind01_p8
import _speckind01_p9
import _speckind01_p10
import _speckind01_p11
import _speckind01_p12
import _speckind01_p13
import _speckind01_p14
import _speckind01_p15
import _speckind01_p16
import _speckind01_p17

PARTS = (_speckind01_p1, _speckind01_p2, _speckind01_p3, _speckind01_p4,
         _speckind01_p5, _speckind01_p6, _speckind01_p7, _speckind01_p8,
         _speckind01_p9, _speckind01_p10, _speckind01_p11, _speckind01_p12,
         _speckind01_p13, _speckind01_p14, _speckind01_p15, _speckind01_p16,
         _speckind01_p17)


def fill(add):
    for part in PARTS:
        part.part(add)
