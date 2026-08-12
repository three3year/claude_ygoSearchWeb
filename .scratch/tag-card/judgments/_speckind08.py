# -*- coding: utf-8 -*-
"""票44 判定 SPEC 彙整(kind-08,300 張)。"""
import _speckind08_p1
import _speckind08_p2
import _speckind08_p3
import _speckind08_p4
import _speckind08_p5
import _speckind08_p6
import _speckind08_p7
import _speckind08_p8
import _speckind08_p9
import _speckind08_p10
import _speckind08_p11
import _speckind08_p12
import _speckind08_p13
import _speckind08_p14
import _speckind08_p15
import _speckind08_p16

PARTS = (
    _speckind08_p1,
    _speckind08_p2,
    _speckind08_p3,
    _speckind08_p4,
    _speckind08_p5,
    _speckind08_p6,
    _speckind08_p7,
    _speckind08_p8,
    _speckind08_p9,
    _speckind08_p10,
    _speckind08_p11,
    _speckind08_p12,
    _speckind08_p13,
    _speckind08_p14,
    _speckind08_p15,
    _speckind08_p16,
)


def fill(add):
    for part in PARTS:
        part.part(add)
