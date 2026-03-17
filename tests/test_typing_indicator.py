"""Tests for the Telegram 'typing' indicator helpers in OpenClawGateway.

Covered:
  _typing_loop  — sends 'typing' action; silences errors; stops on cancellation
  _typing       — context manager starts the loop task and cancels it on exit
  handle_prompt — verifies send_chat_action is called for any real text message
"""
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import OpenClawGateway
from aiogram.types import Message, Chat, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gateway() -> OpenClawGateway:
    """Return a bare OpenClawGateway with only the bot mocked (no real I/O)."""
    gw = OpenClawGateway.__new__(OpenClawGateway)
    gw.bot = MagicMock()
    gw.bot.send_chat_action = AsyncMock()
    return gw


def _make_message(chat_id: int = 12345) -> MagicMock:
    """Build a minimal mock Message with a .chat.id attribute."""
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock(spec=Chat)
    msg.chat.id = chat_id
    return msg


# ---------------------------------------------------------------------------
# _typing_loop
# ---------------------------------------------------------------------------

def test_typing_loop_sends_typing_action():
    """_typing_loop must call send_chat_action(chat_id, action='typing') at least once."""
    gw = _make_gateway()

    async def run():
        task = asyncio.create_task(gw._typing_loop(42))
        await asyncio.sleep(0.05)  # let it fire at least once
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())

    assert gw.bot.send_chat_action.called, "send_chat_action was never called"
    call_kwargs = gw.bot.send_chat_action.call_args
    assert call_kwargs.kwargs.get("action") == "typing" or \
           (call_kwargs.args and call_kwargs.args[-1] == "typing"), \
        f"Expected action='typing', got: {call_kwargs}"
    print("[PASS] _typing_loop sends 'typing' action")


def test_typing_loop_uses_correct_chat_id():
    """_typing_loop must pass the provided chat_id to send_chat_action."""
    gw = _make_gateway()
    expected_chat_id = 99999

    async def run():
        task = asyncio.create_task(gw._typing_loop(expected_chat_id))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())

    call_kwargs = gw.bot.send_chat_action.call_args
    actual_chat_id = (
        call_kwargs.kwargs.get("chat_id")
        or (call_kwargs.args[0] if call_kwargs.args else None)
    )
    assert actual_chat_id == expected_chat_id, \
        f"Expected chat_id={expected_chat_id}, got {actual_chat_id}"
    print("[PASS] _typing_loop uses correct chat_id")


def test_typing_loop_refreshes_multiple_times():
    """_typing_loop must send typing more than once over a longer window (≥2 calls in ~9 s).

    We patch asyncio.sleep to run instantly so the test stays fast.
    """
    gw = _make_gateway()
    sleep_count = [0]

    original_sleep = asyncio.sleep

    async def fast_sleep(delay):
        sleep_count[0] += 1
        if sleep_count[0] >= 3:
            raise asyncio.CancelledError()
        await original_sleep(0)  # yield control but don't actually wait

    async def run():
        with patch("asyncio.sleep", side_effect=fast_sleep):
            task = asyncio.create_task(gw._typing_loop(1))
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(run())

    call_count = gw.bot.send_chat_action.call_count
    assert call_count >= 2, f"Expected ≥2 typing calls, got {call_count}"
    print(f"[PASS] _typing_loop refreshes multiple times ({call_count} calls)")


def test_typing_loop_silences_send_error():
    """_typing_loop must NOT propagate exceptions from send_chat_action."""
    gw = _make_gateway()
    gw.bot.send_chat_action = AsyncMock(side_effect=Exception("Network error"))

    async def run():
        task = asyncio.create_task(gw._typing_loop(1))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # If we reach here without an unhandled exception, the test passes

    asyncio.run(run())
    print("[PASS] _typing_loop silences send_chat_action errors")


def test_typing_loop_stops_on_cancellation():
    """_typing_loop must finish cleanly (no CancelledError leak) when cancelled."""
    gw = _make_gateway()

    async def run():
        task = asyncio.create_task(gw._typing_loop(1))
        await asyncio.sleep(0.02)
        task.cancel()
        # await must not raise CancelledError
        await task  # _typing_loop suppresses CancelledError internally

    asyncio.run(run())
    print("[PASS] _typing_loop stops cleanly on cancellation")


# ---------------------------------------------------------------------------
# _typing context manager
# ---------------------------------------------------------------------------

def test_typing_context_manager_sends_action():
    """_typing context manager must trigger at least one send_chat_action call."""
    gw = _make_gateway()
    msg = _make_message(chat_id=77)

    async def run():
        async with gw._typing(msg):
            await asyncio.sleep(0.05)

    asyncio.run(run())

    assert gw.bot.send_chat_action.called, "send_chat_action not called inside _typing"
    print("[PASS] _typing context manager triggers send_chat_action")


def test_typing_context_manager_cancels_after_exit():
    """After the _typing block completes, no more typing actions should be sent."""
    gw = _make_gateway()
    msg = _make_message(chat_id=88)

    async def run():
        async with gw._typing(msg):
            await asyncio.sleep(0.02)
        # reset counter after block exit
        call_count_at_exit = gw.bot.send_chat_action.call_count
        await asyncio.sleep(0.1)  # wait longer than one loop interval
        call_count_after = gw.bot.send_chat_action.call_count
        return call_count_at_exit, call_count_after

    count_exit, count_after = asyncio.run(run())
    assert count_exit == count_after, (
        f"send_chat_action kept firing after context exit: "
        f"{count_exit} → {count_after}"
    )
    print("[PASS] _typing context manager stops typing after block exit")


def test_typing_context_manager_cancels_on_exception():
    """_typing must cancel the typing task even if the wrapped block raises."""
    gw = _make_gateway()
    msg = _make_message(chat_id=99)
    raised = False

    async def run():
        nonlocal raised
        try:
            async with gw._typing(msg):
                await asyncio.sleep(0.02)
                raise RuntimeError("simulated failure")
        except RuntimeError:
            raised = True
        count_at_exit = gw.bot.send_chat_action.call_count
        await asyncio.sleep(0.1)
        count_after = gw.bot.send_chat_action.call_count
        return count_at_exit, count_after

    count_exit, count_after = asyncio.run(run())
    assert raised, "Exception was not propagated"
    assert count_exit == count_after, (
        f"Typing kept firing after exception: {count_exit} → {count_after}"
    )
    print("[PASS] _typing context manager cancels on exception inside block")


# ---------------------------------------------------------------------------
# handle_prompt integration (lightweight smoke test)
# ---------------------------------------------------------------------------

def test_handle_prompt_calls_typing():
    """handle_prompt must call send_chat_action with action='typing'."""
    gw = _make_gateway()
    gw.admin_id = 1
    gw._intent_cache = {}
    gw._session_msg_count = 0

    # Patch all heavy dependencies so we never actually hit vLLM / Telegram
    inner_called = [False]

    async def fake_inner(message, prompt):
        inner_called[0] = True
        await asyncio.sleep(0.05)  # simulate brief processing

    gw._handle_prompt_inner = fake_inner  # type: ignore[assignment]

    # Build a minimal fake Message
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock()
    msg.chat.id = 55
    msg.from_user = MagicMock()
    msg.from_user.id = 1  # matches admin_id
    msg.text = "Тестовый промпт"
    msg.bot = gw.bot

    asyncio.run(gw.handle_prompt(msg))

    assert inner_called[0], "_handle_prompt_inner was never called"
    assert gw.bot.send_chat_action.called, \
        "send_chat_action was NOT called — typing indicator missing in handle_prompt"
    print("[PASS] handle_prompt triggers typing indicator")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_typing_loop_sends_typing_action,
        test_typing_loop_uses_correct_chat_id,
        test_typing_loop_refreshes_multiple_times,
        test_typing_loop_silences_send_error,
        test_typing_loop_stops_on_cancellation,
        test_typing_context_manager_sends_action,
        test_typing_context_manager_cancels_after_exit,
        test_typing_context_manager_cancels_on_exception,
        test_handle_prompt_calls_typing,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"[ERROR] {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("All tests PASSED!")
    else:
        print("Some tests FAILED!")
        sys.exit(1)
