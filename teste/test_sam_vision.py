from __future__ import annotations

import os
import sys

from _client import ensure_status, ok, post, print_section


def main() -> None:
    image_path = os.getenv("KY_SAM_IMAGE", "").strip()
    prompt = os.getenv("KY_SAM_PROMPT", "segment the main object").strip()
    if not image_path:
        raise SystemExit(
            "请先设置环境变量 KY_SAM_IMAGE=/绝对路径/图片文件，再执行该测试脚本。"
        )

    print_section("SAM Vision Endpoint")
    response = post(
        "/vision/sam-segment",
        data={
            "image_path": image_path,
            "instruction": prompt,
            "top_k": 3,
        },
    )
    ensure_status(response, 200)
    payload = response.json()
    if not payload.get("ok"):
        raise SystemExit(f"SAM 接口返回失败: {payload}")
    ok(
        "SAM 分割完成 "
        f"detection_count={payload.get('detection_count')} "
        f"overlay={payload.get('overlay_path')}"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
