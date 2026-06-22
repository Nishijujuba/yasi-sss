from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path(r"D:\Project\yasi\docs\superpowers\diagrams\yasi-forced-alignment-sequence.png")
FONT_REGULAR = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

WIDTH = 3400
LEFT = 120
RIGHT = 120
TOP = 70
HEADER_H = 280
ROW_H = 82
BOTTOM = 110

PARTICIPANTS = [
    ("Op", "操作人\nCodex"),
    ("Job", "后台启动器\nlaunch_job"),
    ("Align", "编排脚本\nalign_transcript"),
    ("T", "官方文本\ntranscript.json"),
    ("Media", "音频探测\nsection audio"),
    ("Loc", "定位证据\nWhisper/JSON"),
    ("Work", "工作产物\n待删除/work"),
    ("Ffm", "切片器\nffmpeg"),
    ("Qwen", "对齐 Worker\nQwen"),
    ("Rev", "验收轨迹\nreview JSON"),
    ("Val", "收口校验\nfinalize/validate"),
    ("Mon", "监控器\nmonitor"),
]

STEPS = [
    ("Op", "Align", "dry-run --section N：先做路径、时长、切片计划预演", "预演与定位计划"),
    ("Align", "T", "读取 official section text；后续展示文本只认 transcript.json", "预演与定位计划"),
    ("Align", "Media", "ffprobe 探测 section audio 时长", "预演与定位计划"),
    ("Align", "Op", "短音频 <=180s：返回全段 direct alignment 计划", "预演与定位计划"),
    ("Align", "Loc", "长音频或显式 localize：加载/生成 ASR localization", "预演与定位计划"),
    ("Align", "Loc", "定位 contentStartSeconds，建立官方 token 到时间的粗锚点", "预演与定位计划"),
    ("Align", "Work", "写 localized slice plan 预览：audio range + official token range", "预演与定位计划"),
    ("Op", "Job", "launch_alignment_job.py：重活放后台 GPU job", "后台 GPU 对齐"),
    ("Job", "Work", "写 job JSON、PID、stdout/stderr 路径", "后台 GPU 对齐"),
    ("Job", "Align", "后台执行 align_transcript.py 正式对齐", "后台 GPU 对齐"),
    ("Op", "Mon", "monitor_alignment_job.py --latest：短轮询读取状态", "后台 GPU 对齐"),
    ("Mon", "Work", "读取 job、日志、localization、slice qwen/log artifacts", "后台 GPU 对齐"),
    ("Mon", "Op", "返回快照：GPU/日志尾巴/缺失切片/错误信号", "后台 GPU 对齐"),
    ("Align", "Media", "正式运行前再次校验路径、音频时长、GPU preflight", "后台 GPU 对齐"),
    ("Align", "Loc", "校验 sourceAudio 防 stale；分数低于阈值则停在 Qwen 前", "后台 GPU 对齐"),
    ("Align", "Work", "持久化 enriched localization JSON 和 plan hash", "后台 GPU 对齐"),
    ("Align", "Ffm", "循环每个 localized slice：按 audioStart/audioEnd 切 WAV", "后台 GPU 对齐"),
    ("Ffm", "Work", "产出 section-NN.slice-MMM.wav", "后台 GPU 对齐"),
    ("Align", "Work", "写切片 official text；文本来自 transcript.json 的 token range", "后台 GPU 对齐"),
    ("Align", "Qwen", "Qwen.align(slice wav, slice official text, English)", "后台 GPU 对齐"),
    ("Qwen", "Work", "写 slice qwen JSON 和 wrapper log", "后台 GPU 对齐"),
    ("Align", "Work", "合并切片：slice-local time offset 回原音频，overlap 按 token identity 去重", "后台 GPU 对齐"),
    ("Align", "Rev", "映射到官方 token identity，写 draft timings 与 alignment-review.json", "后台 GPU 对齐"),
    ("Op", "Rev", "人或 subagent 审 uncertain mappings：数字、拼写、货币、连字符、撇号", "Review 与发布门禁"),
    ("Rev", "Op", "durable 验收写回 JSON：approved 或 corrected", "Review 与发布门禁"),
    ("Op", "Val", "align_transcript.py --finalize-review 生成 transcript-timings.json", "Review 与发布门禁"),
    ("Val", "T", "核对官方 token identity；禁止用模型文本改 transcript.json", "Review 与发布门禁"),
    ("Val", "Work", "写最终 frontend asset：transcript-timings.json", "Review 与发布门禁"),
    ("Op", "Val", "validate_timings：review trace、单调时间、全 section、localization/slice provenance", "Review 与发布门禁"),
    ("Val", "Op", "发布门禁结果：通过才给前端消费；失败回到修复/重跑", "Review 与发布门禁"),
]

COLORS = {
    "ink": "#111827",
    "muted": "#475569",
    "line": "#64748b",
    "blue": "#2563eb",
    "border": "#cbd5e1",
    "box": "#ffffff",
    "group1": "#eaf3ff",
    "group2": "#fff5df",
    "group3": "#eaf8ee",
}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        bbox = draw.textbbox((0, 0), trial, font=text_font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_arrow(draw: ImageDraw.ImageDraw, x1: int, x2: int, y: int, color: str) -> None:
    draw.line((x1, y, x2, y), fill=color, width=4)
    size = 14
    if x2 >= x1:
        points = [(x2, y), (x2 - size, y - size // 2), (x2 - size, y + size // 2)]
    else:
        points = [(x2, y), (x2 + size, y - size // 2), (x2 + size, y + size // 2)]
    draw.polygon(points, fill=color)


def group_bounds() -> list[tuple[str, int, int]]:
    bounds: list[tuple[str, int, int]] = []
    current = ""
    start = 0
    for index, (_, _, _, group) in enumerate(STEPS):
        if group != current:
            if current:
                bounds.append((current, start, index - 1))
            current = group
            start = index
    bounds.append((current, start, len(STEPS) - 1))
    return bounds


def render() -> None:
    height = TOP + HEADER_H + len(STEPS) * ROW_H + BOTTOM
    image = Image.new("RGB", (WIDTH, height), "#f8fafc")
    draw = ImageDraw.Draw(image)

    title_font = font(FONT_BOLD, 46)
    subtitle_font = font(FONT_REGULAR, 27)
    participant_font = font(FONT_BOLD, 23)
    small_font = font(FONT_REGULAR, 23)
    label_font = font(FONT_REGULAR, 25)
    group_font = font(FONT_BOLD, 27)

    draw.text((LEFT, TOP), "Archived Yasi Forced Alignment Skill 时序图", font=title_font, fill=COLORS["ink"])
    draw.text(
        (LEFT, TOP + 62),
        "归档说明：该 Qwen 路线已由 ADR-0008 的 ASR Timing Reconciliation 替代；本图仅保留历史流程。",
        font=subtitle_font,
        fill=COLORS["muted"],
    )

    usable_width = WIDTH - LEFT - RIGHT
    x_step = usable_width / (len(PARTICIPANTS) - 1)
    xpos = {pid: int(LEFT + index * x_step) for index, (pid, _) in enumerate(PARTICIPANTS)}

    box_width = 240
    box_height = 78
    box_y = TOP + 120
    lifeline_top = box_y + box_height
    lifeline_bottom = height - BOTTOM + 20

    for pid, label in PARTICIPANTS:
        x = xpos[pid]
        draw.rounded_rectangle(
            (x - box_width // 2, box_y, x + box_width // 2, box_y + box_height),
            radius=12,
            fill=COLORS["box"],
            outline=COLORS["border"],
            width=2,
        )
        lines = label.split("\n")
        yy = box_y + (box_height - len(lines) * 28) / 2 - 1
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=participant_font)
            draw.text((x - (bbox[2] - bbox[0]) / 2, yy), line, font=participant_font, fill=COLORS["ink"])
            yy += 28

    group_fill = {
        "预演与定位计划": COLORS["group1"],
        "后台 GPU 对齐": COLORS["group2"],
        "Review 与发布门禁": COLORS["group3"],
    }
    for group, start_index, end_index in group_bounds():
        y1 = TOP + HEADER_H + start_index * ROW_H - 18
        y2 = TOP + HEADER_H + (end_index + 1) * ROW_H - 12
        draw.rounded_rectangle((LEFT - 45, y1, WIDTH - RIGHT + 45, y2), radius=20, fill=group_fill[group], outline="#d6dee8", width=2)
        label_x2 = WIDTH - RIGHT + 28
        label_x1 = label_x2 - 310
        draw.rounded_rectangle((label_x1, y1 + 12, label_x2, y1 + 52), radius=10, fill="#ffffff", outline="#d6dee8", width=1)
        bbox = draw.textbbox((0, 0), group, font=group_font)
        draw.text((label_x1 + (310 - (bbox[2] - bbox[0])) / 2, y1 + 17), group, font=group_font, fill=COLORS["ink"])

    for pid, _ in PARTICIPANTS:
        x = xpos[pid]
        y = lifeline_top + 12
        while y < lifeline_bottom:
            draw.line((x, y, x, min(y + 18, lifeline_bottom)), fill="#94a3b8", width=2)
            y += 32

    for index, (source, target, text, _) in enumerate(STEPS):
        y = TOP + HEADER_H + index * ROW_H + 31
        x1 = xpos[source]
        x2 = xpos[target]
        direction = 1 if x2 >= x1 else -1
        start_x = x1 + direction * 18
        end_x = x2 - direction * 18
        draw_arrow(draw, start_x, end_x, y, COLORS["blue"])

        midpoint = (x1 + x2) / 2
        if abs(x2 - x1) > 470:
            label_width = max(360, min(abs(x2 - x1) - 40, 780))
        else:
            label_width = 460
        lines = wrap_text(draw, text, label_font, int(label_width))
        text_height = len(lines) * 29 + 8
        box_x1 = max(LEFT - 20, midpoint - label_width / 2 - 14)
        box_x2 = min(WIDTH - RIGHT + 20, midpoint + label_width / 2 + 14)
        if box_x2 - box_x1 < label_width + 28:
            if box_x1 <= LEFT:
                box_x2 = box_x1 + label_width + 28
            else:
                box_x1 = box_x2 - label_width - 28
        label_box = (box_x1, y - text_height - 8, box_x2, y - 8)
        text_y = y - text_height - 3
        draw.rounded_rectangle(label_box, radius=8, fill="#ffffff", outline="#e2e8f0", width=1)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=label_font)
            draw.text((midpoint - (bbox[2] - bbox[0]) / 2, text_y), line, font=label_font, fill=COLORS["ink"])
            text_y += 29

    footer = "输出：localization JSON / localized slice plan / slice qwen JSON / alignment-review.json / transcript-timings.json；失败信号通过 monitor 和 validator 暴露。"
    draw.text((LEFT, height - 70), footer, font=small_font, fill=COLORS["muted"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, "PNG", optimize=True)
    print(str(OUT))
    print(f"{WIDTH}x{height}")


if __name__ == "__main__":
    render()
