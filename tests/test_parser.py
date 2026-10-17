# -*- coding: utf-8 -*-
"""最小测试：规则引擎对样本文本的提取结果。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trip_compare.extract import load
from trip_compare.parser import parse

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "..", "samples")


def test_sample_a():
    p = parse(load(os.path.join(SAMPLES, "A-雪山秘境6日.txt")))
    assert p.days == 6, p.days
    assert p.route and "拉萨" in "".join(p.route)
    assert p.gifts, "应提取到赠送项"
    assert p.stays, "应提取到住宿"


def test_sample_b():
    p = parse(load(os.path.join(SAMPLES, "B-川西环线8日.txt")))
    assert (p.days, p.nights) == (8, 7), (p.days, p.nights)
    assert "滑雪" in p.skiing or "滑雪" in "".join(p.gifts)
    assert p.photography, "应提取到旅拍口径"


if __name__ == "__main__":
    test_sample_a()
    test_sample_b()
    print("OK: 2 tests passed")
