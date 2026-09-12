from pyrogram import enums, types

from carlotta import app, config, lang
from carlotta.core.lang import lang_codes


class Inline:
    def __init__(self):
        self.ikm = types.InlineKeyboardMarkup
        self.ikb = types.InlineKeyboardButton
        self.button_styles = {
            "default": enums.ButtonStyle.DEFAULT,
            "primary": enums.ButtonStyle.PRIMARY,
            "danger": enums.ButtonStyle.DANGER,
            "success": enums.ButtonStyle.SUCCESS,
        }

    def button(self, *args, style: str = "default", **kwargs):
        return self.ikb(*args, style=self.button_styles[style], **kwargs)

    def cancel_dl(self, text) -> types.InlineKeyboardMarkup:
        return self.ikm([[self.button(text=text, callback_data="cancel_dl", style="danger")]])

    def controls(
        self,
        chat_id: int,
        status: str = None,
        timer: str = None,
        remove: bool = False,
    ) -> types.InlineKeyboardMarkup:
        keyboard = []
        if status:
            keyboard.append(
                [self.button(text=status, callback_data=f"controls status {chat_id}", style="primary")]
            )
        elif timer:
            keyboard.append(
                [self.button(text=timer, callback_data=f"controls status {chat_id}", style="primary")]
            )

        if not remove:
            keyboard.append(
                [
                    self.button(text="▷", callback_data=f"controls resume {chat_id}", style="primary"),
                    self.button(text="II", callback_data=f"controls pause {chat_id}", style="primary"),
                    self.button(text="⥁", callback_data=f"controls replay {chat_id}", style="primary"),
                    self.button(text="‣‣I", callback_data=f"controls skip {chat_id}", style="primary"),
                    self.button(text="▢", callback_data=f"controls stop {chat_id}", style="primary"),
                ]
            )
            keyboard.append(
                [
                    self.button(
                        text="➕ Add to Playlist",
                        callback_data=f"playlist savecurrent {chat_id}",
                        style="success",
                    )
                ]
            )
        return self.ikm(keyboard)

    def help_markup(
        self, _lang: dict, back: bool = False
    ) -> types.InlineKeyboardMarkup:
        if back:
            rows = [
                [
                    self.button(text=_lang["back"], callback_data="help back", style="primary"),
                    self.button(text=_lang["close"], callback_data="help close", style="danger"),
                ]
            ]
        else:
            cbs = [
                "admins",
                "auth",
                "blist",
                "lang",
                "lyrics",
                "ping",
                "play",
                "queue",
                "search",
                "shuffle",
                "stats",
                "sudo",
                "volume",
            ]
            buttons = [
                self.button(
                    text=_lang[f"help_{cb}"], callback_data=f"help {cb}", style="primary"
                )
                for cb in cbs
            ]
            rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]

        return self.ikm(rows)

    def lang_markup(self, _lang: str) -> types.InlineKeyboardMarkup:
        langs = lang.get_languages()
        buttons = [
            self.button(
                text=f"{name} ({code}) {'✔️' if code == _lang else ''}",
                callback_data=f"lang_change {code}",
                style="success" if code == _lang else "default",
            )
            for code, name in langs.items()
        ]
        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
        return self.ikm(rows)

    def ping_markup(self, text: str) -> types.InlineKeyboardMarkup:
        return self.ikm([[self.button(text=text, url=config.SUPPORT_CHAT, style="primary")]])

    def play_queued(
        self, chat_id: int, item_id: str, _text: str
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.button(
                        text=_text, callback_data=f"controls force {chat_id} {item_id}", style="success"
                    )
                ]
            ]
        )

    def play_usage_markup(
        self, user_id: int, playlist_text: str, close_text: str
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.button(
                        text=playlist_text,
                        callback_data=f"playlist open {user_id} saved 0",
                        style="primary",
                    ),
                    self.button(
                        text=close_text,
                        callback_data=f"playlist close {user_id}",
                        style="danger",
                    ),
                ]
            ]
        )

    def queue_markup(
        self, chat_id: int, _text: str, playing: bool
    ) -> types.InlineKeyboardMarkup:
        _action = "pause" if playing else "resume"
        return self.ikm(
            [[self.button(text=_text, callback_data=f"controls {_action} {chat_id} q", style="success" if not playing else "primary")]]
        )

    def settings_markup(
        self,
        lang: dict,
        admin_only: bool,
        cmd_delete: bool,
        autoplay: bool,
        clean_mode: bool,
        language: str,
        stream_mode: str,
        chat_id: int,
        ) -> types.InlineKeyboardMarkup:
        _on = lang["autoplay_switch_on"]
        _off = lang["autoplay_switch_off"]
        return self.ikm(
            [
                [
                    self.button(
                        text=lang["play_mode"] + " ➜",
                        callback_data="settings",
                        style="primary",
                    ),
                    self.button(
                        text=_on if admin_only else _off,
                        callback_data="settings play",
                        style="success" if admin_only else "danger",
                    ),
                ],
                [
                    self.button(
                        text=lang["cmd_delete"] + " ➜",
                        callback_data="settings cmd_delete",
                        style="primary",
                    ),
                    self.button(
                        text=_on if cmd_delete else _off,
                        callback_data="settings cmd_delete_toggle",
                        style="success" if cmd_delete else "danger",
                    ),
                ],
                [
                    self.button(
                        text=lang["autoplay"] + " ➜",
                        callback_data="settings autoplay",
                        style="primary",
                    ),
                    self.button(
                        text=_on if autoplay else _off,
                        callback_data="settings autoplay_toggle",
                        style="success" if autoplay else "danger",
                    ),
                ],
                [
                    self.button(
                        text=lang["clean_mode"] + " ➜",
                        callback_data="settings clean",
                        style="primary",
                    ),
                    self.button(
                        text=_on if clean_mode else _off,
                        callback_data="settings clean_toggle",
                        style="success" if clean_mode else "danger",
                    ),
                ],
                [
                    self.button(
                        text=lang["language"],
                        callback_data="settings language",
                        style="primary",
                    ),
                    self.button(
                        text=language.upper(),
                        callback_data="settings language",
                        style="default",
                    ),
                ],
                [
                    self.button(
                        text=lang["stream_mode"],
                        callback_data="settings stream_mode",
                        style="primary",
                    ),
                    self.button(
                        text=stream_mode.title(),
                        callback_data="settings stream_mode",
                        style="default",
                    ),
                ],
                [
                    self.button(
                        text=lang["close"],
                        callback_data="settings close",
                        style="danger",
                    )
                ],
            ]
        )

    def autoplay_markup(
        self, _lang: dict, chat_id: int, enabled: bool
    ) -> types.InlineKeyboardMarkup:
        enable_text = _lang["autoplay_switch_on"]
        disable_text = _lang["autoplay_switch_off"]
        return self.ikm(
            [
                [
                    self.button(
                        text=enable_text,
                        callback_data=f"autoplay enable {chat_id}",
                        style="success" if not enabled else "primary",
                    ),
                    self.button(
                        text=disable_text,
                        callback_data=f"autoplay disable {chat_id}",
                        style="danger" if enabled else "primary",
                    ),
                ],
                [
                    self.button(
                        text=_lang["close"],
                        callback_data=f"autoplay close {chat_id}",
                        style="danger",
                    )
                ],
            ]
        )


buttons = Inline()
