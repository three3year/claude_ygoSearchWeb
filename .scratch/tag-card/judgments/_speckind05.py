# -*- coding: utf-8 -*-
"""票41 判定 SPEC 彙整(kind-05,300 張)。"""
import _speckind05_p1
import _speckind05_p2
import _speckind05_p3
import _speckind05_p4
import _speckind05_p5
import _speckind05_p6
import _speckind05_p7
import _speckind05_p8
import _speckind05_p9
import _speckind05_p10
import _speckind05_p11
import _speckind05_p12
import _speckind05_p13
import _speckind05_p14
import _speckind05_p15
import _speckind05_p16

PARTS = (_speckind05_p1, _speckind05_p2, _speckind05_p3, _speckind05_p4, _speckind05_p5, _speckind05_p6, _speckind05_p7, _speckind05_p8, _speckind05_p9, _speckind05_p10, _speckind05_p11, _speckind05_p12, _speckind05_p13, _speckind05_p14, _speckind05_p15, _speckind05_p16)


def fill(add):
    for part in PARTS:
        part.part(add)
