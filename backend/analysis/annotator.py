from PIL import Image, ImageDraw, ImageFont

from backend.config import ANNOTATED_DIR
from backend.models import LayoutResult


RED = "#E53935"
LIGHT_RED = (229, 57, 53, 80)
GRAY = "#9E9E9E"
WHITE = "#FFFFFF"
BLANK_W = 26
BLANK_H = 22


def _get_font(size):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _draw_dashed_rect(draw, xy, fill, width):
    x1, y1, x2, y2 = xy
    dash, gap = 8, 6
    for x in range(x1, x2, dash + gap):
        draw.line([(x, y1), (min(x + dash, x2), y1)], fill=fill, width=width)
        draw.line([(x, y2), (min(x + dash, x2), y2)], fill=fill, width=width)
    for y in range(y1, y2, dash + gap):
        draw.line([(x1, y), (x1, min(y + dash, y2))], fill=fill, width=width)
        draw.line([(x2, y), (x2, min(y + dash, y2))], fill=fill, width=width)


def _norm_to_pixel(b, img_w, img_h):
    return {
        "x": int(b.x * img_w),
        "y": int(b.y * img_h),
        "w": int(b.w * img_w),
        "h": int(b.h * img_h),
    }


def _clamp(v, lo, hi):
    return max(lo, min(v, hi))


def generate_annotated_image(image_path: str, run_id: str, layout: LayoutResult) -> str:
    img = Image.open(image_path)
    img_w, img_h = img.size

    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    font_label = _get_font(12)
    font_legend = _get_font(13)

    total_areas = 0

    for sec_idx, section in enumerate(layout.sections, 1):
        sb = _norm_to_pixel(section.bbox, img_w, img_h)
        sx, sy, sw, sh = sb["x"], sb["y"], sb["w"], sb["h"]
        print(f"  Section {sec_idx}: {section.title} -> pixel ({sx},{sy},{sw},{sh})")
        _draw_dashed_rect(
            draw, (sx - 5, sy - 3, sx + sw + 5, sy + sh + 3),
            fill=GRAY, width=1)

        for prob_idx, problem in enumerate(section.problems, 1):
            pn = problem.problem_number
            label = f"T{sec_idx}-{pn}"

            areas_count = len(problem.answer_areas)
            if areas_count == 0:
                print(f"    {label}: 0 answer_areas (SKIPPED)")
                continue

            print(f"    {label}: {areas_count} answer_areas")
            for area in problem.answer_areas:
                ab = _norm_to_pixel(area.bbox, img_w, img_h)
                ax, ay, aw, ah = ab["x"], ab["y"], ab["w"], ab["h"]

                if aw < 8 or ah < 8:
                    aw, ah = BLANK_W, BLANK_H

                ax = _clamp(ax, 0, img_w - aw)
                ay = _clamp(ay, 0, img_h - ah)

                print(f"      area: ({ax},{ay},{aw},{ah})")
                overlay_draw.rectangle(
                    [ax, ay, ax + aw, ay + ah], fill=LIGHT_RED)
                draw.rectangle(
                    [ax - 1, ay - 1, ax + aw + 1, ay + ah + 1],
                    outline=RED, width=2)
                total_areas += 1

            if problem.answer_areas:
                first = _norm_to_pixel(problem.answer_areas[0].bbox, img_w, img_h)
                ax, ay = first["x"], first["y"]
            elif problem.bbox:
                pb = _norm_to_pixel(problem.bbox, img_w, img_h)
                ax, ay = pb["x"], pb["y"]
            else:
                continue

            tb = draw.textbbox((0, 0), label, font=font_label)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            lx = ax + 4
            ly = ay - th - 4
            if ly < 0:
                ly = ay + 4
            if lx + tw + 4 > img_w:
                lx = ax - tw - 4

            draw.rectangle(
                [lx - 2, ly - 2, lx + tw + 4, ly + th + 4],
                fill=WHITE)
            draw.text((lx, ly), label, fill=RED, font=font_label)

    img = Image.alpha_composite(img, overlay)

    legend_x = img_w - 240
    legend_y = 8
    legend_w = 232
    legend_h = 36
    legend_draw = ImageDraw.Draw(img, "RGBA")
    legend_draw.rectangle(
        [legend_x, legend_y, legend_x + legend_w, legend_y + legend_h],
        fill=(255, 255, 255, 210),
        outline="#CCCCCC",
    )
    legend_draw.rectangle(
        [legend_x + 8, legend_y + 10, legend_x + 26, legend_y + 26],
        fill=LIGHT_RED,
        outline=RED,
        width=2,
    )
    legend_draw.text(
        (legend_x + 34, legend_y + 8),
        "需作答区域 (AI归一化坐标)",
        fill=RED,
        font=font_legend,
    )

    img = img.convert("RGB")

    output_path = f"{ANNOTATED_DIR}/{run_id}.jpg"
    img.save(output_path, quality=95)

    print(f"  Total areas drawn: {total_areas}")
    return output_path
