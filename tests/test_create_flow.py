from types import SimpleNamespace

import pytest
from aiogram.types import LinkPreviewOptions, MessageEntity

from handlers import create_flow
from states import CreateGiveaway


class RecordingState:
    def __init__(self, data=None) -> None:
        self.data = data or {}
        self.current_state = None

    async def get_data(self):
        return self.data

    async def set_state(self, value) -> None:
        self.current_state = value


class RecordingMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.answers: list[tuple[tuple, dict]] = []

    async def answer(self, *args, **kwargs) -> None:
        self.answers.append((args, kwargs))


@pytest.mark.asyncio
async def test_capture_post_saves_exact_rich_content_and_presentation(
    monkeypatch,
) -> None:
    message = RecordingMessage()
    message.caption = "🔥 Авторський текст\nЦитата"
    message.caption_entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id="premium-emoji",
        ),
        MessageEntity(type="blockquote", offset=20, length=6),
    ]
    message.photo = [SimpleNamespace(file_id="small"), SimpleNamespace(file_id="large")]
    message.video = None
    message.animation = None
    message.show_caption_above_media = True
    message.has_media_spoiler = True
    message.link_preview_options = LinkPreviewOptions(
        url="https://example.com",
        show_above_text=True,
    )
    message.from_user = SimpleNamespace(id=123)
    state = RecordingState({"gid": 7})
    saved: list[tuple] = []

    async def set_post(*args):
        saved.append(args)

    monkeypatch.setattr(create_flow, "set_post", set_post)

    await create_flow.capture_post(message, state)

    assert len(saved) == 1
    assert saved[0][0] == 7
    assert saved[0][2] == message.caption
    assert [entity["type"] for entity in saved[0][3]] == [
        "custom_emoji",
        "blockquote",
    ]
    assert saved[0][4:9] == (
        "photo",
        "large",
        True,
        True,
        {"url": "https://example.com", "show_above_text": True},
    )
    assert state.current_state == CreateGiveaway.waiting_button_text


@pytest.mark.asyncio
async def test_whitespace_button_text_is_rejected(monkeypatch) -> None:
    message = RecordingMessage("   ")
    state = RecordingState({"gid": 7})
    saved: list[str] = []

    async def save(_message, _state, text):
        saved.append(text)

    monkeypatch.setattr(create_flow, "_save_button_text_and_ask_style", save)

    await create_flow.custom_btn(message, state)

    assert saved == []
    assert "порожнім" in message.answers[0][0][0]


@pytest.mark.asyncio
async def test_style_selection_goes_directly_to_requirements(monkeypatch) -> None:
    message = RecordingMessage()
    state = RecordingState({"gid": 7})
    answers: list[tuple[tuple, dict]] = []
    saved: list[tuple[int, str]] = []

    async def set_design(gid, style):
        saved.append((gid, style))

    async def show_requirements(received_message, received_state):
        assert received_message is message
        assert received_state is state
        await received_state.set_state(CreateGiveaway.waiting_requirements)

    async def callback_answer(*args, **kwargs):
        answers.append((args, kwargs))

    callback = SimpleNamespace(
        data="btnstyle:success",
        message=message,
        answer=callback_answer,
    )
    monkeypatch.setattr(create_flow, "set_button_design", set_design)
    monkeypatch.setattr(create_flow, "_show_requirements", show_requirements)

    await create_flow.choose_button_style(callback, state)

    assert saved == [(7, "success")]
    assert state.current_state == CreateGiveaway.waiting_requirements
    assert answers == [((), {})]
    assert not hasattr(CreateGiveaway, "waiting_button_icon")
