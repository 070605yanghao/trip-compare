# -*- coding: utf-8 -*-
"""PDF / 纯文本提取。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Doc:
    path: str
    pages: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.pages)

    @property
    def name(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]


def _clean(t: str) -> str:
    """去掉 PDF 字体编码里常见的孤立代理字符。"""
    return t.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def load(path: str) -> Doc:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _load_pdf(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return Doc(path=path, pages=[f.read()])


def _load_pdf(path: str) -> Doc:
    from pypdf import PdfReader  # 延迟导入：纯文本模式不需要 pypdf

    reader = PdfReader(path)
    pages = [_clean(p.extract_text() or "") for p in reader.pages]
    return Doc(path=path, pages=pages)


def gather(inputs: list[str]) -> list[str]:
    """把输入（文件或目录）展开为受支持的文件列表。"""
    out: list[str] = []
    for it in inputs:
        if os.path.isdir(it):
            for fn in sorted(os.listdir(it)):
                if os.path.splitext(fn)[1].lower() in (".pdf", ".txt"):
                    out.append(os.path.join(it, fn))
        elif os.path.isfile(it):
            out.append(it)
    return out
