import datetime
from types import SimpleNamespace

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramServerError,
)
from aiogram.methods import GetChatMember
from aiogram.types import Chat, Message, MessageOriginChannel, MessageOriginChat, User

from services.subscription import SubscriptionCheckUnavailable, is_member_everywhere
from utils.formatting import forwarded_chat_id


def _message_with_origin(origin) -> Message:
    return Message(
        message_id=1,
        date=datetime.datetime.now(datetime.UTC),
        chat=Chat(id=42, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Owner"),
        forward_origin=origin,
    )


def test_forwarded_chat_id_supports_current_channel_and_chat_origins() -> None:
    now = datetime.datetime.now(datetime.UTC)
    channel_message = _message_with_origin(
        MessageOriginChannel(
            type="channel",
            date=now,
            chat=Chat(id=-100123, type="channel", title="Channel"),
            message_id=9,
        )
    )
    chat_message = _message_with_origin(
        MessageOriginChat(
            type="chat",
            date=now,
            sender_chat=Chat(id=-100456, type="supergroup", title="Group"),
        )
    )

    assert forwarded_chat_id(channel_message) == "-100123"
    assert forwarded_chat_id(chat_message) == "-100456"


class MembershipErrorBot:
    def __init__(self, error_type) -> None:
        self.error_type = error_type

    async def get_chat_member(self, chat_id, user_id):
        method = GetChatMember(chat_id=chat_id, user_id=user_id)
        if self.error_type is TelegramForbiddenError:
            raise TelegramForbiddenError(method=method, message="forbidden")
        if self.error_type is TelegramServerError:
            raise TelegramServerError(method=method, message="server error")
        raise TelegramBadRequest(method=method, message="bad request")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [TelegramBadRequest, TelegramForbiddenError, TelegramServerError],
)
async def test_membership_permission_errors_are_not_false_unsubscribes(
    error_type,
) -> None:
    with pytest.raises(SubscriptionCheckUnavailable):
        await is_member_everywhere(
            MembershipErrorBot(error_type),
            77,
            ["-100123"],
            retry=False,
        )


@pytest.mark.asyncio
async def test_restricted_chat_member_is_allowed_when_still_a_member() -> None:
    class RestrictedMemberBot:
        async def get_chat_member(self, chat_id, user_id):
            return SimpleNamespace(status="restricted", is_member=True)

    assert await is_member_everywhere(RestrictedMemberBot(), 77, ["-100123"])
