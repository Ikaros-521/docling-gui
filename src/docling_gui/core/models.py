"""模型工件定位与 HF 端点兜底。

- 内置模型：打包时把 docling 的布局/表格模型放进 _internal/docling-models，
  运行时自动识别并作为 artifacts_path，PDF/图片转换完全离线。
  也可用环境变量 DOCLING_ARTIFACTS_PATH 指向外部模型目录（例如单独下载的
  模型包解压位置），优先级高于内置目录。
- 镜像兜底：huggingface.co 不可达时自动切换 https://hf-mirror.com。
  HF_ENDPOINT 是在 huggingface_hub 首次导入时读取的，因此必须在任何
  docling/huggingface_hub 导入之前调用 ensure_hf_endpoint()。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HF_DIRECT = "https://huggingface.co"
_HF_MIRROR = "https://hf-mirror.com"
_MODELS_DIR_NAME = "docling-models"
# artifacts 布局的哨兵：docling 按 repo_id.replace('/', '--') 在
# artifacts_path 下寻址，布局模型目录存在即视为完整工件集
_SENTINEL = "docling-project--docling-layout-heron"


def bundled_artifacts_path() -> Path | None:
    """返回可用的模型工件目录：环境变量 > 打包内置 > None（跟随在线下载）。"""
    candidates: list[Path] = []
    env = os.environ.get("DOCLING_ARTIFACTS_PATH")
    if env:
        candidates.append(Path(env))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / _MODELS_DIR_NAME)
    for cand in candidates:
        if (cand / _SENTINEL).is_dir():
            return cand
    return None


def ensure_hf_endpoint() -> None:
    """直连 HF 失败时把 HF_ENDPOINT 切到镜像源（幂等，可重复调用）。"""
    if os.environ.get("HF_ENDPOINT"):
        return
    if _reachable(_HF_DIRECT):
        return
    os.environ["HF_ENDPOINT"] = _HF_MIRROR


def _reachable(url: str, timeout: float = 4.0) -> bool:
    try:
        import urllib.request

        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False
