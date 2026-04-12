"""Tests for CdpEventCollector.

Uses a fake CDP session to avoid needing a real browser.
"""
from __future__ import annotations

import base64
import gzip
import queue
from typing import Any
from unittest.mock import patch

from src.live.cdp_collector import CdpEventCollector
from src.live.proto_douyin import (
    ChatMessage,
    GiftMessage,
    MemberMessage,
    Message,
    PushFrame,
    Response,
)

# ---------------------------------------------------------------------------
# Helpers to build fake protobuf payloads (mirrors what Douyin server sends)
# ---------------------------------------------------------------------------


def _make_binary_frame(method: str, inner_payload: bytes) -> str:
    """Build a base64-encoded WSS binary frame the way Douyin sends it."""
    msg = Message(method=method, payload=inner_payload)
    response = Response(messages_list=[msg], need_ack=False)
    compressed = gzip.compress(bytes(response))
    push_frame = PushFrame(payload_type="msg", payload=compressed)
    return base64.b64encode(bytes(push_frame)).decode()


def _rich_user(
    nick: str,
    uid: int = 0,
    display_id: str = "",
    sec_uid: str = "",
    gender: int = 0,
    follow_status: int = 0,
    follower_count: int = 0,
    pay_grade_level: int = 0,
    fans_club_name: str = "",
    fans_club_level: int = 0,
) -> Any:
    from src.live.proto_douyin import FansClub, FansClubData, FollowInfo, PayGrade, User

    return User(
        id=uid,
        nick_name=nick,
        display_id=display_id,
        sec_uid=sec_uid,
        gender=gender,
        follow_info=FollowInfo(follow_status=follow_status, follower_count=follower_count),
        pay_grade=PayGrade(level=pay_grade_level),
        fans_club=FansClub(data=FansClubData(club_name=fans_club_name, level=fans_club_level)),
    )


def _chat_payload(user: str, content: str) -> bytes:
    from src.live.proto_douyin import User

    return bytes(ChatMessage(content=content, user=User(nick_name=user, id=12345)))


def _gift_payload(
    user: str,
    gift_name: str,
    count: int,
    repeat_count: int = 0,
    diamond_count: int = 0,
) -> bytes:
    from src.live.proto_douyin import GiftStruct, User

    return bytes(
        GiftMessage(
            user=User(nick_name=user),
            gift=GiftStruct(name=gift_name, diamond_count=diamond_count),
            combo_count=count,
            repeat_count=repeat_count,
        )
    )


def _member_payload(user: str, enter_type: int = 0, is_set_to_admin: bool = False) -> bytes:
    from src.live.proto_douyin import User

    return bytes(
        MemberMessage(
            user=User(nick_name=user, id=99),
            enter_type=enter_type,
            is_set_to_admin=is_set_to_admin,
        )
    )


def _like_payload(user: str, count: int) -> bytes:
    from src.live.proto_douyin import LikeMessage, User

    return bytes(LikeMessage(user=User(nick_name=user), count=count))


def _social_payload(user: str, action: int = 1) -> bytes:
    from src.live.proto_douyin import SocialMessage, User

    return bytes(SocialMessage(user=User(nick_name=user), action=action))


def _fansclub_payload(user: str, content: str, type_: int) -> bytes:
    from src.live.proto_douyin import FansclubMessage, User

    return bytes(FansclubMessage(user=User(nick_name=user), content=content, type=type_))


def _stats_payload(online: int, total_pv: str) -> bytes:
    from src.live.proto_douyin import RoomUserSeqMessage

    return bytes(RoomUserSeqMessage(total=online, total_pv_for_anchor=total_pv))


def _control_payload(status: int) -> bytes:
    from src.live.proto_douyin import ControlMessage

    return bytes(ControlMessage(status=status))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseFrame:
    """Unit tests for the internal frame parser — no browser needed."""

    def setup_method(self):
        self.collector = CdpEventCollector(out_queue=queue.Queue(), cdp_url="ws://localhost:9222")

    def test_parses_chat_message(self):
        payload = _make_binary_frame("WebcastChatMessage", _chat_payload("Alice", "hello"))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "danmaku"
        assert events[0].user == "Alice"
        assert events[0].text == "hello"

    def test_parses_gift_message(self):
        payload = _make_binary_frame("WebcastGiftMessage", _gift_payload("Bob", "Rose", 3))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "gift"
        assert events[0].user == "Bob"
        assert events[0].gift == "Rose"

    def test_parses_member_message(self):
        payload = _make_binary_frame("WebcastMemberMessage", _member_payload("Carol"))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "enter"
        assert events[0].user == "Carol"

    def test_parses_like_message(self):
        payload = _make_binary_frame("WebcastLikeMessage", _like_payload("Dave", 15))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "like"
        assert events[0].user == "Dave"
        assert events[0].value == 15

    def test_parses_social_message(self):
        payload = _make_binary_frame("WebcastSocialMessage", _social_payload("Eve"))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "follow"
        assert events[0].user == "Eve"

    def test_parses_fansclub_join(self):
        payload = _make_binary_frame("WebcastFansclubMessage", _fansclub_payload("Frank", "加入了粉丝团", 2))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "fansclub"
        assert events[0].user == "Frank"
        assert events[0].text == "加入了粉丝团"

    def test_parses_room_stats(self):
        payload = _make_binary_frame("WebcastRoomUserSeqMessage", _stats_payload(1000, "5.2万"))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "stats"
        assert events[0].value == 1000
        assert events[0].total_pv == "5.2万"

    def test_parses_control_end(self):
        payload = _make_binary_frame("WebcastControlMessage", _control_payload(3))
        events = self.collector._parse_frame(payload)
        assert len(events) == 1
        assert events[0].type == "end"

    def test_ignores_control_non_end(self):
        payload = _make_binary_frame("WebcastControlMessage", _control_payload(1))
        events = self.collector._parse_frame(payload)
        assert events == []

    def test_ignores_unknown_method(self):
        payload = _make_binary_frame("WebcastUnknownMessage", b"garbage")
        events = self.collector._parse_frame(payload)
        assert events == []

    def test_returns_empty_on_corrupt_data(self):
        events = self.collector._parse_frame("not-valid-base64!!!")
        assert events == []

    def test_multiple_messages_in_one_frame(self):
        chat = Message(method="WebcastChatMessage", payload=_chat_payload("A", "hi"))
        enter = Message(method="WebcastMemberMessage", payload=_member_payload("B"))
        response = Response(messages_list=[chat, enter], need_ack=False)
        compressed = gzip.compress(bytes(response))
        push_frame = PushFrame(payload_type="msg", payload=compressed)
        encoded = base64.b64encode(bytes(push_frame)).decode()

        events = self.collector._parse_frame(encoded)
        assert len(events) == 2
        assert events[0].type == "danmaku"
        assert events[1].type == "enter"


class TestCdpCollectorLifecycle:
    """Integration-style tests with mocked Playwright."""

    def test_start_stop(self):
        q = queue.Queue()
        collector = CdpEventCollector(out_queue=q, cdp_url="ws://localhost:9222")
        with patch("playwright.async_api.async_playwright"):
            collector.start()
            collector.stop()
        # Should not raise

    def test_events_put_on_queue(self):
        """Simulate a CDP event arriving and verify it lands on the queue."""
        q = queue.Queue()
        collector = CdpEventCollector(out_queue=q, cdp_url="ws://localhost:9222")

        payload = _make_binary_frame("WebcastChatMessage", _chat_payload("Alice", "hello"))
        # Directly call the handler as if CDP fired the event
        collector._on_ws_frame({"response": {"payloadData": payload}})

        event = q.get_nowait()
        assert event.type == "danmaku"
        assert event.text == "hello"


class TestUserInfo:
    """Tests that user_info is populated with rich metadata on each event type."""

    def setup_method(self):
        self.collector = CdpEventCollector(out_queue=queue.Queue(), cdp_url="ws://localhost:9222")

    def _parse(self, method: str, payload: bytes):
        frame = _make_binary_frame(method, payload)
        events = self.collector._parse_frame(frame)
        assert len(events) == 1
        return events[0]

    def test_chat_user_info_basic_fields(self):
        from src.live.proto_douyin import ChatMessage

        user = _rich_user(
            "Alice",
            uid=111,
            display_id="alice_dy",
            sec_uid="sec_abc",
            gender=2,
        )
        payload = bytes(ChatMessage(content="hi", user=user))
        event = self._parse("WebcastChatMessage", payload)
        assert event.user_info is not None
        assert event.user_info.uid == 111
        assert event.user_info.display_id == "alice_dy"
        assert event.user_info.sec_uid == "sec_abc"
        assert event.user_info.gender == 2

    def test_chat_user_info_follow_and_grade(self):
        from src.live.proto_douyin import ChatMessage

        user = _rich_user(
            "Bob",
            uid=222,
            follow_status=1,
            follower_count=5000,
            pay_grade_level=8,
        )
        payload = bytes(ChatMessage(content="yo", user=user))
        event = self._parse("WebcastChatMessage", payload)
        ui = event.user_info
        assert ui.follow_status == 1
        assert ui.follower_count == 5000
        assert ui.pay_grade == 8

    def test_chat_user_info_fans_club(self):
        from src.live.proto_douyin import ChatMessage

        user = _rich_user(
            "Carol",
            uid=333,
            fans_club_name="Alice fan club",
            fans_club_level=3,
        )
        payload = bytes(ChatMessage(content="hello", user=user))
        event = self._parse("WebcastChatMessage", payload)
        ui = event.user_info
        assert ui.fans_club_name == "Alice fan club"
        assert ui.fans_club_level == 3

    def test_gift_has_user_info_and_combo(self):
        from src.live.proto_douyin import GiftStruct

        user = _rich_user("Dave", uid=444, pay_grade_level=15)
        payload = bytes(
            GiftMessage(
                user=user,
                gift=GiftStruct(name="SuperStar", diamond_count=52),
                combo_count=10,
                repeat_count=3,
            )
        )
        event = self._parse("WebcastGiftMessage", payload)
        assert event.user_info is not None
        assert event.user_info.uid == 444
        assert event.user_info.pay_grade == 15
        assert event.combo_count == 10
        assert event.gift_count == 3
        assert event.value == 52

    def test_enter_has_user_info_and_enter_type(self):

        user = _rich_user("Eve", uid=555, gender=1)
        payload = bytes(MemberMessage(user=user, enter_type=6, is_set_to_admin=False))
        event = self._parse("WebcastMemberMessage", payload)
        assert event.user_info is not None
        assert event.user_info.uid == 555
        assert event.user_info.gender == 1
        assert event.enter_type == 6

    def test_enter_is_admin_flag(self):

        user = _rich_user("Frank", uid=666)
        payload = bytes(MemberMessage(user=user, enter_type=0, is_set_to_admin=True))
        event = self._parse("WebcastMemberMessage", payload)
        assert event.user_info.is_admin is True

    def test_follow_vs_share_via_action(self):
        from src.live.proto_douyin import SocialMessage

        user = _rich_user("Grace", uid=777)
        # action=1 → follow
        payload_follow = bytes(SocialMessage(user=user, action=1))
        event_follow = self._parse("WebcastSocialMessage", payload_follow)
        assert event_follow.type == "follow"

        # action=3 → share
        payload_share = bytes(SocialMessage(user=user, action=3))
        frame = _make_binary_frame("WebcastSocialMessage", payload_share)
        events = self.collector._parse_frame(frame)
        assert len(events) == 1
        assert events[0].type == "share"

    def test_like_has_user_info(self):
        from src.live.proto_douyin import LikeMessage

        user = _rich_user("Heidi", uid=888)
        payload = bytes(LikeMessage(user=user, count=7))
        event = self._parse("WebcastLikeMessage", payload)
        assert event.user_info is not None
        assert event.user_info.uid == 888
        assert event.value == 7

    def test_fansclub_has_user_info(self):
        from src.live.proto_douyin import FansclubMessage

        user = _rich_user("Ivan", uid=999, fans_club_level=5, fans_club_name="big fan")
        payload = bytes(FansclubMessage(user=user, content="加入了粉丝团", type=2))
        event = self._parse("WebcastFansclubMessage", payload)
        assert event.user_info is not None
        assert event.user_info.uid == 999
        assert event.user_info.fans_club_level == 5

    def test_stats_total_pv_field(self):
        from src.live.proto_douyin import RoomUserSeqMessage

        payload = bytes(RoomUserSeqMessage(total=2000, total_pv_for_anchor="12.3万"))
        event = self._parse("WebcastRoomUserSeqMessage", payload)
        assert event.total_pv == "12.3万"
        assert event.value == 2000


class TestRawField:
    """Every parsed event carries the full proto payload as a dict in .raw."""

    def setup_method(self):
        self.collector = CdpEventCollector(out_queue=queue.Queue(), cdp_url="ws://localhost:9222")

    def _parse(self, method: str, payload: bytes):
        frame = _make_binary_frame(method, payload)
        events = self.collector._parse_frame(frame)
        assert len(events) == 1
        return events[0]

    def test_chat_raw_contains_content(self):
        from src.live.proto_douyin import User

        payload = bytes(ChatMessage(content="hello raw", user=User(nick_name="Alice", id=1)))
        event = self._parse("WebcastChatMessage", payload)
        assert event.raw is not None
        assert event.raw["content"] == "hello raw"

    def test_chat_raw_contains_nested_user(self):
        from src.live.proto_douyin import User

        payload = bytes(ChatMessage(content="x", user=User(nick_name="Bob", id=42, gender=1)))
        event = self._parse("WebcastChatMessage", payload)
        assert event.raw["user"]["gender"] == 1

    def test_gift_raw_contains_combo_and_gift_struct(self):
        from src.live.proto_douyin import GiftStruct, User

        payload = bytes(
            GiftMessage(
                user=User(nick_name="Carol"),
                gift=GiftStruct(name="Rose", diamond_count=10),
                combo_count=5,
            )
        )
        event = self._parse("WebcastGiftMessage", payload)
        assert event.raw["comboCount"] == "5"  # betterproto serializes uint64 as str
        assert event.raw["gift"]["name"] == "Rose"

    def test_fansclub_raw_exposes_type(self):
        from src.live.proto_douyin import FansclubMessage, User

        payload = bytes(FansclubMessage(user=User(nick_name="Dave"), content="升级了", type=1))
        event = self._parse("WebcastFansclubMessage", payload)
        # type=1 means upgrade — not promoted to a dedicated field, available via raw
        assert event.raw["type"] == 1

    def test_stats_raw_contains_popularity(self):
        from src.live.proto_douyin import RoomUserSeqMessage

        payload = bytes(RoomUserSeqMessage(total=500, popularity=9999, total_pv_for_anchor="1万"))
        event = self._parse("WebcastRoomUserSeqMessage", payload)
        assert event.raw["popularity"] == "9999"  # betterproto serializes uint64 as str

    def test_end_event_has_no_raw(self):
        from src.live.proto_douyin import ControlMessage

        payload = bytes(ControlMessage(status=3))
        event = self._parse("WebcastControlMessage", payload)
        assert event.raw is None
