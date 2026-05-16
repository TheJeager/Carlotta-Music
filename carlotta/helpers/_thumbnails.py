import os
import aiohttp
from datetime import timedelta
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps, ImageStat)

from carlotta import config
from carlotta.helpers import Track

# Auto create cache folder, no need to create manually
os.makedirs("cache", exist_ok=True)

class Thumbnail:
    def __init__(self):
        try:
            self.font_title = ImageFont.truetype("carlotta/helpers/Raleway-Bold.ttf", 58)
            self.font_artist = ImageFont.truetype("carlotta/helpers/Inter-Light.ttf", 32)
            self.font_album = ImageFont.truetype("carlotta/helpers/Inter-Light.ttf", 28)
            self.font_time = ImageFont.truetype("carlotta/helpers/Inter-Light.ttf", 24)
            self.font_badge = ImageFont.truetype("carlotta/helpers/Inter-Light.ttf", 22)
        except:
            # Match font size even if custom fonts are missing
            self.font_title = ImageFont.load_default(size=58)
            self.font_artist = ImageFont.load_default(size=32)
            self.font_album = ImageFont.load_default(size=28)
            self.font_time = ImageFont.load_default(size=24)
            self.font_badge = ImageFont.load_default(size=22)
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def save_thumb(self, output_path, url):
        async with self.session.get(url) as resp:
            with open(output_path, "wb") as f:
                f.write(await resp.read())
        return output_path

    def round_corner(self, image, radius):
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, image.size[0], image.size[1]], radius=radius, fill=255)
        output = Image.new("RGBA", image.size, (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(mask)
        return output

    def truncate(self, text, font, max_width, draw):
        text = str(text)
        if draw.textlength(text, font=font) <= max_width:
            return text
        while draw.textlength(text + "...", font=font) > max_width and len(text) > 1:
            text = text[:-1]
        return text.strip() + "..."

    def center_x(self, text, font, width, draw):
        return int((width - draw.textlength(text, font=font)) // 2)


    def format_album(self, song: Track):
        album = getattr(song, "album", None)
        if album:
            return f"Album • {album}"
        if song.channel_name:
            return f"Album • {song.channel_name}"
        return "Album • Single"

    def format_duration(self, duration_sec):
        try:
            total = max(int(duration_sec), 0)
        except Exception:
            return "00:00"

        if total >= 3600:
            return str(timedelta(seconds=total))
        minutes, seconds = divmod(total, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def get_dominant_tint(self, source):
        # Keep it lightweight: small sample + average color
        sample = source.convert("RGB").resize((80, 80), Image.Resampling.BILINEAR)
        r, g, b = [int(c) for c in ImageStat.Stat(sample).mean]
        return (
            max(18, min(150, int(r * 0.48))),
            max(28, min(180, int(g * 0.52))),
            max(38, min(210, int(b * 0.58))),
            140,
        )

    def get_palette(self, source):
        sample = source.convert("RGB").resize((120, 120), Image.Resampling.BILINEAR)
        colors = sample.getcolors(sample.size[0] * sample.size[1]) or []
        if not colors:
            return (255, 45, 146), (142, 97, 255), (255, 176, 84)

        colors.sort(key=lambda item: item[0], reverse=True)
        top_colors = [c for _, c in colors[:8]]

        def clamp(color, min_channel=36):
            return tuple(max(min_channel, min(235, int(ch))) for ch in color)

        primary = clamp(top_colors[0])
        secondary = clamp(top_colors[2] if len(top_colors) > 2 else top_colors[-1])
        accent = clamp(top_colors[4] if len(top_colors) > 4 else top_colors[-1], min_channel=64)
        return primary, secondary, accent

    def blend_with_white(self, color, amount=0.35):
        return tuple(min(255, int(ch + ((255 - ch) * amount))) for ch in color)

    def blend_with_black(self, color, amount=0.35):
        return tuple(max(0, int(ch * (1 - amount))) for ch in color)

    def draw_text_with_shadow(self, draw, xy, text, font, fill, shadow=(0, 0, 0, 145), offset=(0, 2)):
        draw.text((xy[0] + offset[0], xy[1] + offset[1]), text, font=font, fill=shadow)
        draw.text(xy, text, font=font, fill=fill)

    def make_vertical_gradient(self, size, top_color, bottom_color):
        width, height = size
        gradient = Image.new("RGBA", size, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(gradient)
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(
                int((top_color[i] * (1 - ratio)) + (bottom_color[i] * ratio))
                for i in range(4)
            )
            gdraw.line([(0, y), (width, y)], fill=color)
        return gradient

    async def generate(self, song: Track, size=(1280, 720)):
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"

            # Return cached thumbnail if already generated
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)
            thumb = Image.open(temp).convert("RGBA").resize(size, Image.Resampling.LANCZOS)

            # Apple Music-inspired layered backdrop
            primary, secondary, accent = self.get_palette(thumb)
            bg = thumb.filter(ImageFilter.GaussianBlur(74))
            bg = ImageEnhance.Brightness(bg).enhance(0.31)
            bg = ImageEnhance.Color(bg).enhance(1.3)
            image = bg.convert("RGBA")
            tint = Image.new("RGBA", size, self.get_dominant_tint(thumb))
            image = Image.alpha_composite(image, tint)

            # cinematic top-to-bottom wash for better depth
            top_tint = (*self.blend_with_black(primary, 0.25), 90)
            bottom_tint = (*self.blend_with_black(secondary, 0.62), 210)
            image = Image.alpha_composite(image, self.make_vertical_gradient(size, top_tint, bottom_tint))

            # gradient glow blobs
            glow = Image.new("RGBA", size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            gdraw.ellipse([40, 40, 640, 650], fill=(*primary, 86))
            gdraw.ellipse([690, -120, 1400, 580], fill=(*secondary, 84))
            gdraw.ellipse([520, 340, 1180, 980], fill=(*accent, 72))
            glow = glow.filter(ImageFilter.GaussianBlur(95))
            image = Image.alpha_composite(image, glow)

            # Main floating glass card
            card = (84, 44, 1196, 676)
            card_layer = Image.new("RGBA", size, (0, 0, 0, 0))
            cdraw = ImageDraw.Draw(card_layer)
            cdraw.rounded_rectangle(card, radius=46, fill=(12, 12, 16, 164), outline=(255, 255, 255, 86), width=2)
            card_layer = card_layer.filter(ImageFilter.GaussianBlur(0.6))
            image = Image.alpha_composite(image, card_layer)

            # Refined top highlight for a cleaner Apple Music-style card header
            header_glow = Image.new("RGBA", size, (0, 0, 0, 0))
            hdraw = ImageDraw.Draw(header_glow)
            hdraw.rounded_rectangle((118, 86, 1162, 176), radius=34, fill=(255, 255, 255, 16))
            hdraw.rounded_rectangle((118, 86, 1162, 176), radius=34, outline=(255, 255, 255, 40), width=1)
            header_glow = header_glow.filter(ImageFilter.GaussianBlur(3.5))
            image = Image.alpha_composite(image, header_glow)

            # Album art area
            art_size = 430
            art_x = 146
            art_y = (size[1] - art_size) // 2
            frame = (art_x, art_y, art_x + art_size, art_y + art_size)
            shadow = Image.new("RGBA", size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                [frame[0] + 8, frame[1] + 12, frame[2] + 8, frame[3] + 12],
                radius=52, fill=(0, 0, 0, 170)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(30))
            image = Image.alpha_composite(image, shadow)

            # Art frame
            frame_layer = Image.new("RGBA", size, (0, 0, 0, 0))
            fdraw = ImageDraw.Draw(frame_layer)
            fdraw.rounded_rectangle(frame, radius=48, fill=(255, 255, 255, 44), outline=(255, 255, 255, 84), width=2)
            image = Image.alpha_composite(image, frame_layer)

            # Clip artwork in rounded square
            inner_w = art_size - 24
            inner_h = art_size - 24
            content = ImageOps.fit(thumb, (inner_w, inner_h), method=Image.Resampling.LANCZOS)
            # Improve album-art clarity for a cleaner, premium thumbnail look
            content = ImageEnhance.Contrast(content).enhance(1.08)
            content = ImageEnhance.Sharpness(content).enhance(1.22)
            content_mask = Image.new("L", (inner_w, inner_h), 0)
            ImageDraw.Draw(content_mask).rounded_rectangle(
                [0, 0, inner_w, inner_h], radius=40, fill=255
            )
            image.paste(content, (frame[0] + 12, frame[1] + 12), content_mask)

            draw = ImageDraw.Draw(image)

            # Metadata area
            info_x = 640
            info_w = 470
            title = self.truncate(song.title, self.font_title, info_w, draw)
            artist = self.truncate(song.channel_name or "Unknown Artist", self.font_artist, info_w, draw)
            album = self.truncate(self.format_album(song), self.font_album, info_w, draw)
            elapsed = self.format_duration(song.time)
            total_duration = str(song.duration or "00:00")

            self.draw_text_with_shadow(draw, (info_x, 218), "NOW PLAYING", self.font_badge, (250, 250, 250, 204))
            self.draw_text_with_shadow(draw, (info_x, 258), title, self.font_title, (255, 255, 255, 244), offset=(0, 3))
            self.draw_text_with_shadow(draw, (info_x, 338), artist, self.font_artist, (239, 239, 239, 230))
            self.draw_text_with_shadow(draw, (info_x, 388), album, self.font_album, (220, 220, 220, 216))

            # Progress bar and controls
            bar_x1, bar_y1 = info_x, 470
            bar_x2, bar_y2 = info_x + info_w, 482
            draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=8, fill=(255, 255, 255, 76))
            progress_ratio = 0
            if song.duration_sec and song.duration_sec > 0:
                progress_ratio = max(0, min(1, int(song.time or 0) / song.duration_sec))
            progress_x = int(bar_x1 + ((bar_x2 - bar_x1) * progress_ratio))
            if progress_x > bar_x1:
                draw.rounded_rectangle([bar_x1, bar_y1, progress_x, bar_y2], radius=8, fill=(*accent, 232))
                knob = (progress_x - 8, bar_y1 - 6, progress_x + 8, bar_y2 + 6)
                draw.ellipse(knob, fill=(255, 255, 255, 242))

            self.draw_text_with_shadow(draw, (bar_x1, 494), elapsed, self.font_time, (235, 235, 235, 228), offset=(0, 1))
            total_x = bar_x2 - int(draw.textlength(total_duration, font=self.font_time))
            self.draw_text_with_shadow(draw, (total_x, 494), total_duration, self.font_time, (235, 235, 235, 228), offset=(0, 1))

            # Stable brand label pinned to the card's lower-left corner
            footer = "Carlotta Music"
            card_left = card[0]
            footer_padding_x = 34
            footer_y = card[3] - 52
            self.draw_text_with_shadow(
                draw,
                (card_left + footer_padding_x, footer_y),
                footer,
                self.font_badge,
                (224, 224, 224, 194),
                offset=(0, 1),
            )

            image.save(output, quality=95)

            # Cleanup temporary file
            try:
                os.remove(temp)
            except:
                pass

            return output

        except Exception as err:
            # uncomment below for debugging if you face issues
            # print(f"Thumbnail generation error: {err}")
            return config.DEFAULT_THUMB