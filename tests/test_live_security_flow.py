import json
import asyncio
import tempfile
import shutil
from pathlib import Path
from src.config import settings
from src.engine.antigravity_bridge import antigravity_bridge, CLI_SETTINGS_PATH


def get_current_deny_list():
    if not CLI_SETTINGS_PATH.exists():
        return []
    data = json.loads(CLI_SETTINGS_PATH.read_text())
    return data.get("permissions", {}).get("deny", [])


async def run_full_security_lifecycle_test():
    """
    Automated end-to-end test of 3 security phases:
    1. Phase 1 (Default Protected): rm attempt is blocked by deny rule, file preserved.
    2. Phase 2 (Force Override): rm attempt allowed, file deleted, settings.json restores deny rules in finally block.
    3. Phase 3 (Auto-revert): next query is blocked again, file preserved.
    """
    temp_dir = tempfile.mkdtemp(prefix="antigravity_test_")
    test_workspace = Path(temp_dir)
    test_user_id = next(iter(settings.allowed_ids_set), 123456789)

    try:
        initial_deny = get_current_deny_list()
        print(f"🔒 Initial Deny rules count: {len(initial_deny)}")
        assert len(initial_deny) > 0, "Initial deny list must not be empty"
        assert "command(rm)" in initial_deny or any("rm" in rule for rule in initial_deny), "rm rule must be in deny list"

        # ----------------------------------------------------
        # PHASE 1: Default Protected Mode (force_override=False)
        # ----------------------------------------------------
        print("\n--- 🛡️ PHASE 1: Protected Mode (force_override=False) ---")
        f1 = test_workspace / "test_security_phase1.txt"
        f1.write_text("PHASE 1 CONTENT")
        assert f1.exists(), "Test file for phase 1 should exist"

        p1_tokens = []
        async for event in antigravity_bridge.stream_chat(
            user_id=test_user_id,
            prompt="Try deleting test_security_phase1.txt via rm. If rm is blocked, do not bypass, stop and report error.",
            project_dir=test_workspace,
            model_name="gemini-3.7-flash",
            effort="low",
            force_override=False
        ):
            if event.event_type == "token":
                p1_tokens.append(str(event.content))

        p1_response = "".join(p1_tokens)
        print("Agent response Phase 1:\n", p1_response.strip())

        assert f1.exists(), "❌ ERROR: File was deleted in Phase 1 despite deny protection!"
        deny_after_p1 = get_current_deny_list()
        assert deny_after_p1 == initial_deny, "❌ Deny list was corrupted after Phase 1"
        print("✅ Phase 1 passed: file preserved, rm blocked, deny list intact.")
        f1.unlink(missing_ok=True)

        # ----------------------------------------------------
        # PHASE 2: Force Override Mode (force_override=True)
        # ----------------------------------------------------
        print("\n--- ⚡ PHASE 2: Force Override (force_override=True) ---")
        f2 = test_workspace / "test_security_phase2.txt"
        f2.write_text("PHASE 2 CONTENT")
        assert f2.exists(), "Test file for phase 2 should exist"

        p2_tokens = []
        async for event in antigravity_bridge.stream_chat(
            user_id=test_user_id,
            prompt="Delete test_security_phase2.txt using terminal command rm.",
            project_dir=test_workspace,
            model_name="gemini-3.7-flash",
            effort="low",
            force_override=True
        ):
            if event.event_type == "token":
                p2_tokens.append(str(event.content))

        p2_response = "".join(p2_tokens)
        print("Agent response Phase 2:\n", p2_response.strip())

        assert not f2.exists(), "❌ ERROR: File was NOT deleted in Phase 2 with Force Override!"
        deny_after_p2 = get_current_deny_list()
        assert deny_after_p2 == initial_deny, "❌ Deny list was NOT restored after Force Override!"
        print("✅ Phase 2 passed: file deleted as requested, Deny list restored instantly.")

        # ----------------------------------------------------
        # PHASE 3: Auto-revert Protection (force_override=False)
        # ----------------------------------------------------
        print("\n--- 🛡️ PHASE 3: Auto-revert protection (force_override=False) ---")
        f3 = test_workspace / "test_security_phase3.txt"
        f3.write_text("PHASE 3 CONTENT")
        assert f3.exists(), "Test file for phase 3 should exist"

        p3_tokens = []
        async for event in antigravity_bridge.stream_chat(
            user_id=test_user_id,
            prompt="Try deleting test_security_phase3.txt via rm. If rm is blocked, stop and report error.",
            project_dir=test_workspace,
            model_name="gemini-3.7-flash",
            effort="low",
            force_override=False
        ):
            if event.event_type == "token":
                p3_tokens.append(str(event.content))

        p3_response = "".join(p3_tokens)
        print("Agent response Phase 3:\n", p3_response.strip())

        assert f3.exists(), "❌ ERROR: Protection did not auto-revert in Phase 3! File was deleted."
        deny_after_p3 = get_current_deny_list()
        assert deny_after_p3 == initial_deny, "❌ Deny list differs from initial after Phase 3"
        print("✅ Phase 3 passed: protection active by default, new file protected.")
        f3.unlink(missing_ok=True)

        print("\n=======================================================")
        print("🎉 ALL 3 SECURITY LIFECYCLE PHASES PASSED 100%!")
        print("=======================================================")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run_full_security_lifecycle_test())
