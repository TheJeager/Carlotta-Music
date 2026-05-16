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
                        text="💾 Save Playlist",
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
                "shuffle",
                "search",
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
                        text=lang["autoplay_title"] + " ➜",
                        callback_data="settings",
                        style="primary",
                    ),
                    self.button(
                        text=_on if autoplay else _off,
                        callback_data="settings autoplay",
                        style="success" if autoplay else "danger",
                    ),
                ],
                [
                    self.button(
                        text=lang["clean_mode"] + " ➜",
                        callback_data="settings",
                        style="primary",
                    ),
                    self.button(
                        text=_on if clean_mode else _off,
                        callback_data="settings clean",
                        style="success" if clean_mode else "danger",
                    ),
                ],
                [
                    self.button(
                        text=lang["cmd_delete"] + " ➜",
                        callback_data="settings",
                        style="primary",
                    ),
                    self.button(
                        text=_on if cmd_delete else _off,
                        callback_data="settings delete",
                        style="success" if cmd_delete else "danger",
                    ),
                ],
                [
                    self.button(
                        text=lang["stream_mode"] + " ➜",
                        callback_data="settings",
                        style="primary",
                    ),
                    self.button(
                        text=lang[f"stream_mode_{stream_mode}"],
                        callback_data="settings quality",
                        style="success",
                    ),
                ],
                [
                    self.button(
                        text=lang["language"] + " ➜",
                        callback_data="settings",
                        style="primary",
                    ),
                    self.button(text=lang_codes[language], callback_data="language", style="success"),
                ],
                [
                    self.button(
                        text=lang["close"],
                        callback_data=f"autoplay close {chat_id}",
                        style="danger",
                    )
                ],
            ]
        )

    def autoplay_markup(
        self, _lang: dict, chat_id: int, enabled: bool
    ) -> types.InlineKeyboardMarkup:
        enable_text = (
            f"✓ {_lang['autoplay_enable']}" if enabled else _lang["autoplay_enable"]
        )
        disable_text = (
            f"✓ {_lang['autoplay_disable']}" if not enabled else _lang["autoplay_disable"]
        )
        return self.ikm(
            [
                [
                    self.button(
                        text=enable_text,
                        callback_data=f"autoplay enable {chat_id}",
                        style="primary"
                    ),
                    self.button(
                        text=disable_text,
                        callback_data=f"autoplay disable {chat_id}",
                        style="primary"
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

    def search_again_markup(self) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [[self.button(text="🔍 Search Again", switch_inline_query_current_chat="")]]
        )

    def search_markup(
        self, results: list, _lang: dict, user_id: int
    ) -> types.InlineKeyboardMarkup:
        rows = []
        for index, item in enumerate(results, start=1):
            rows.append(
                [
                    self.button(
                        text=f"{index}. {item['title'][:40]}",
                        callback_data=f"search {user_id} play {item['id']}",
                        style="primary",
                    )
                ]
            )
        rows.append(
            [
                self.button(
                    text=_lang["close"],
                    callback_data=f"search {user_id} close",
                    style="danger",
                )
            ]
        )
        return self.ikm(rows)

    def lyrics_markup(
        self, _lang: dict, user_id: int
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.button(
                        text=_lang["close"],
                        callback_data=f"lyrics {user_id} close",
                        style="danger",
                    )
                ]
            ]
        )

    def quality_markup(
        self, _lang: dict, chat_id: int, selected: str
    ) -> types.InlineKeyboardMarkup:
        modes = ["performance", "balanced", "best"]
        rows = []
        for mode in modes:
            label = _lang[f"stream_mode_{mode}"]
            if selected == mode:
                label = f"✓ {label}"
            rows.append(
                [
                    self.button(
                        text=label,
                        callback_data=f"quality set {chat_id} {mode}",
                        style="success" if selected == mode else "primary",
                    )
                ]
            )

        rows.append(
            [
                self.button(
                    text=_lang["close"],
                    callback_data=f"quality close {chat_id}",
                    style="danger",
                )
            ]
        )

        return self.ikm(rows)

    def clean_markup(
        self, _lang: dict, chat_id: int, enabled: bool
    ) -> types.InlineKeyboardMarkup:
        enable_text = (
            f"✓ {_lang['autoplay_enable']}" if enabled else _lang["autoplay_enable"]
        )
        disable_text = (
            f"✓ {_lang['autoplay_disable']}" if not enabled else _lang["autoplay_disable"]
        )
        return self.ikm(
            [
                [
                    self.button(
                        text=enable_text,
                        callback_data=f"clean enable {chat_id}",
                        style="primary",
                    ),
                    self.button(
                        text=disable_text,
                        callback_data=f"clean disable {chat_id}",
                        style="primary",
                    ),
                ],
                [
                    self.button(
                        text=_lang["close"],
                        callback_data=f"clean close {chat_id}",
                        style="danger",
                    )
                ],
            ]
        )

    def start_key(
        self, lang: dict, private: bool = False
    ) -> types.InlineKeyboardMarkup:
        rows = [
            [
                self.button(
                    text=lang["add_me"],
                    url=f"https://t.me/{app.username}?startgroup=true",
                    style="success",
                )
            ],
            [self.button(text=lang["help"], callback_data="help", style="primary")],
            [
                self.button(text=lang["support"], url=config.SUPPORT_CHAT, style="primary"),
                self.button(text=lang["channel"], url=config.SUPPORT_CHANNEL, style="primary"),
            ],
        ]
        if private:
            pass  # source button removed
        else:
            rows += [[self.button(text=lang["language"], callback_data="language", style="success")]]
        return self.ikm(rows)

    def playlist_markup(
        self,
        user_id: int,
        section: str,
        index: int,
        total: int,
        saved: bool,
    ) -> types.InlineKeyboardMarkup:
        rows = [
            [
                self.button(
                    text="⟨",
                    callback_data=f"playlist nav {user_id} {section} {index - 1}",
                    style="primary",
                ),
                self.button(
                    text=f"{index + 1}/{total}",
                    callback_data=f"playlist noop {user_id}",
                    style="default",
                ),
                self.button(
                    text="⟩",
                    callback_data=f"playlist nav {user_id} {section} {index + 1}",
                    style="primary",
                ),
            ],
            [
                self.button(
                    text="Saved",
                    callback_data=f"playlist switch {user_id} saved 0",
                    style="primary" if section == "saved" else "default",
                ),
                self.button(
                    text="Recent",
                    callback_data=f"playlist switch {user_id} history 0",
                    style="primary",
                ),
            ],
        ]

        action = "delete" if saved else "save"
        action_text = "🗑 Remove" if saved else "💾 Save"
        rows.append(
            [
                self.button(
                    text="♫ Play",
                    callback_data=f"playlist play {user_id} {section} {index}",
                    style="primary",
                ),
                self.button(
                    text=action_text,
                    callback_data=f"playlist {action} {user_id} {section} {index}",
                    style="primary",
                ),
            ]
        )

        rows.append(
            [
                self.button(
                    text="Close",
                    callback_data=f"playlist close {user_id}",
                    style="primary",
                )
            ]
        )
        return self.ikm(rows)

    def playlist_empty_markup(
        self,
        user_id: int,
        section: str,
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.button(
                        text="Saved",
                        callback_data=f"playlist switch {user_id} saved 0",
                        style="primary" if section == "saved" else "default",
                    ),
                    self.button(
                        text="Recent",
                        callback_data=f"playlist switch {user_id} history 0",
                        style="primary",
                    ),
                ],
                [
                    self.button(
                        text="Close",
                        callback_data=f"playlist close {user_id}",
                        style="danger",
                    )
                ],
            ]
        )
