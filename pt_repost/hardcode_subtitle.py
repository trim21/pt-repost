import pathlib
from typing import NamedTuple

import PIL.Image
import regex
from rapidocr_onnxruntime import RapidOCR


class Point(NamedTuple):
    x: int  # 水平方向向右
    y: int  # 垂直方向向下


pattern_chinese = regex.compile(r"\p{script=Han}")


def check_hardcode_chinese_subtitle(image_files: list[pathlib.Path]) -> bool:
    engine = RapidOCR()

    for file in image_files:
        with PIL.Image.open(file) as img:
            size = Point(*img.size)

        result, _ = engine(file)
        if not result:
            continue
        for points, s, _ in result:
            points = [Point(x, y) for x, y in points]
            if points[0].y <= size.y / 2:
                continue
            if len(pattern_chinese.sub("", s)) / len(s) < 0.5:
                return True

    return False
