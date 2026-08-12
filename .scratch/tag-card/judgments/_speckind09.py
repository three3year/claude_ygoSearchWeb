# -*- coding: utf-8 -*-
"""票45 判定 SPEC 彙整(kind-09,300 張)。"""
import _speckind09_p1
import _speckind09_p2
import _speckind09_p3
import _speckind09_p4
import _speckind09_p5
import _speckind09_p6
import _speckind09_p7
import _speckind09_p8
import _speckind09_p9
import _speckind09_p10
import _speckind09_p11
import _speckind09_p12
import _speckind09_p13
import _speckind09_p14
import _speckind09_p15
import _speckind09_p16
import _speckind09_p17

PARTS = (
    _speckind09_p1,
    _speckind09_p2,
    _speckind09_p3,
    _speckind09_p4,
    _speckind09_p5,
    _speckind09_p6,
    _speckind09_p7,
    _speckind09_p8,
    _speckind09_p9,
    _speckind09_p10,
    _speckind09_p11,
    _speckind09_p12,
    _speckind09_p13,
    _speckind09_p14,
    _speckind09_p15,
    _speckind09_p16,
    _speckind09_p17,
)


def fill(add):
    for part in PARTS:
        part.part(add)
