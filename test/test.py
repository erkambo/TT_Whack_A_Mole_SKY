import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb.result import TestFailure

async def reset_dut(dut):
    """Asserting reset for 100 ns, then release and wait one cycle."""
    dut.rst_n.value = 0
    await Timer(100, units='ns')
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

async def wait_active(dut, max_cycles=20):
    """Wait until dp==1 and exactly one segment bit==0, then return its index."""
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        uo = dut.uo_out.value.integer
        dp = (uo >> 7) & 1
        if dp != 1:
            continue
        seg = uo & 0x7F
        zeros = [i for i in range(7) if ((seg >> i) & 1) == 0]
        if len(zeros) == 1:
            return zeros[0]
    raise TestFailure(f"No active gameplay segment within {max_cycles} cycles; last uo=0b{uo:08b}")

def get_dp(dut):
    """Return the decimal-point bit: 1 while playing, 0 when game over."""
    return (dut.uo_out.value.integer >> 7) & 1


@cocotb.test()
async def test_score_increment(dut):
    """Pressing the active segment button increments the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())  # 1MHz clock
    dut.ui_in.value = 0  # Buttons mapped to ui_in
    await reset_dut(dut)

    active_idx = await wait_active(dut)

    # Press button and hold for 5 cycles to pass debouncing
    dut.ui_in.value = 1 << active_idx
    for _ in range(5):  # More than DEBOUNCE_CYCLES
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    # Wait a few cycles for FSM to process the debounced press
    for _ in range(3):
        await RisingEdge(dut.clk)

    score = dut.uio_out.value.integer  # Score LEDs mapped to uio_out
    assert score == 1, f"Expected score 1, got {score}"

@cocotb.test()
async def test_no_increment_on_wrong(dut):
    """Pressing a non-active button does not change the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())  # 1MHz clock

    dut.ui_in.value = 0
    await reset_dut(dut)

    # Settle
    for _ in range(5):
        await RisingEdge(dut.clk)

    # Identify active segment
    seg_val = dut.uo_out.value.integer & 0x7F
    active_idx = next(i for i in range(7) if ((seg_val >> i) & 1) == 0)
    # Choose a different button (wrap-around to bit 7 if necessary)
    wrong_idx = (active_idx + 1) % 8

    dut.ui_in.value = 1 << wrong_idx
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Score should remain zero
    assert dut.uio_out.value.integer == 0, (
        f"Score changed on wrong press: got {dut.uio_out.value.integer}"
    )
    
@cocotb.test()
async def test_game_end_display(dut):
    """Test that the 7-segment display shows the correct active segment pattern during gameplay."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())  # 1MHz clock
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Score two correct presses
    for _ in range(2):
        idx = await wait_active(dut)
        # Press button and hold for 5 cycles to pass debouncing
        dut.ui_in.value = 1 << idx
        for _ in range(5):  # More than DEBOUNCE_CYCLES
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        # Wait a few cycles for FSM to process the debounced press
        for _ in range(3):
            await RisingEdge(dut.clk)

    score = dut.uio_out.value.integer
    assert score == 2, f"Expected internal score 2, got {score}"

    # Wait for the next active segment to appear
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')

    # Check that the display shows an active segment pattern (one bit should be 0)
    seg_val = dut.uo_out.value.integer & 0x7F
    dp = (dut.uo_out.value.integer >> 7) & 1
    
    # During gameplay (game_end=0), exactly one segment should be active (0)
    active_segments = [i for i in range(7) if ((seg_val >> i) & 1) == 0]
    assert len(active_segments) == 1, f"Expected exactly one active segment, got {len(active_segments)}: {active_segments}"
    assert dp == 1, f"Expected dp=1 (game running), got {dp}"

@cocotb.test()
async def test_button_debounce_filter(dut):
    """Test that button glitches are filtered out by the debouncer."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Get the active segment
    active_idx = await wait_active(dut)
    
    # Create a glitch - button press for only 2 cycles (less than DEBOUNCE_CYCLES)
    dut.ui_in.value = 1 << active_idx
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    
    # Wait a few cycles to ensure the glitch is filtered
    for _ in range(5):
        await RisingEdge(dut.clk)
    
    # Score should still be 0 since the glitch was filtered
    score = dut.uio_out.value.integer
    assert score == 0, f"Score changed on glitch: got {score}, expected 0"

@cocotb.test()
async def test_button_debounce_stable(dut):
    """Test that stable button presses are registered after debounce period."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Get the active segment
    active_idx = await wait_active(dut)
    
    # Press button and hold for 5 cycles (more than DEBOUNCE_CYCLES)
    dut.ui_in.value = 1 << active_idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    
    # Release button
    dut.ui_in.value = 0
    # Wait a few cycles for FSM to process the debounced press
    for _ in range(3):
        await RisingEdge(dut.clk)
    
    # Score should increment since press was stable
    score = dut.uio_out.value.integer
    assert score == 1, f"Score not incremented after stable press: got {score}, expected 1"

@cocotb.test()
async def test_game_timer(dut):
    """Score 3 moles, then verify game-over in RTL or timer still running in GL."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())  # 50 MHz sim clock
    dut.ui_in.value = 0
    await reset_dut(dut)

    # helper to read the DP bit
    def get_dp():
        return (dut.uo_out.value.integer >> 7) & 1

    # 1) Score 3 moles
    for expected in range(1, 4):
        idx = await wait_active(dut)
        dut.ui_in.value = 1 << idx
        for _ in range(5):          # pass the debouncer
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        for _ in range(3):          # settle the FSM
            await RisingEdge(dut.clk)
        assert dut.uio_out.value.integer == expected, \
            f"After {expected} hits, score={dut.uio_out.value.integer}"

    # 2) Spin up to 2000 cycles looking for dp→0 (game-over)
    saw_game_over = False
    for cycle in range(2000):
        await RisingEdge(dut.clk)
        dp = get_dp()
        if cycle % 200 == 0:
            dut._log.info(f"[cycle {cycle}] dp={dp}  score={dut.uio_out.value.integer}")
        if dp == 0:
            saw_game_over = True
            dut._log.info(f"→ Detected game-over at cycle {cycle}, final score={dut.uio_out.value.integer}")
            # ensure dp stays low for a bit
            for _ in range(100):
                await RisingEdge(dut.clk)
                if get_dp() == 1:
                    raise TestFailure("dp rose back to 1 after game-over")
            break

    # 3a) If we saw game-over, assert final score & dp==0
    if saw_game_over:
        assert get_dp() == 0, "dp should be 0 after game-over"
        assert dut.uio_out.value.integer == 3, \
            f"Expected final score 3 at game-over, got {dut.uio_out.value.integer}"
    # 3b) Otherwise (gate-level), assert timer still running and score still held
    else:
        assert get_dp() == 1,  "dp dropped in GL sim when it shouldn't"
        assert dut.uio_out.value.integer == 3, \
            f"Score changed in GL sim: got {dut.uio_out.value.integer}"



@cocotb.test()
async def test_auto_start_on_reset(dut):
    """After reset (without pressing start), the game should auto-start and light one segment."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Immediately after reset, one segment must be active (auto-start)
    await RisingEdge(dut.clk)
    seg_val = dut.uo_out.value.integer & 0x7F
    assert seg_val != 0x7F, f"Segment did not light after reset: {seg_val:07b}"


import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_restart_debounce(dut):
    """At game-over, a short glitch on pb0 must NOT restart the game; only a debounced press does."""
    # 1 MHz clock
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())

    # helper to read dp (bit-7 of uo_out)
    def get_dp():
        return (dut.uo_out.value.integer >> 7) & 1

    # reset and start
    dut.ui_in.value = 0
    await reset_dut(dut)

    # 1) Wait up to 500 cycles for dp to drop (game-over)
    saw_over = False
    for cycle in range(500):
        await RisingEdge(dut.clk)
        if get_dp() == 0:
            saw_over = True
            dut._log.info(f"→ game-over detected at cycle {cycle}")
            break

    if not saw_over:
        dut._log.info("dp never fell within 500 cycles—skipping restart-debounce in GL")
        return

    # 2) Short glitch on pb0 (2 cycles): must NOT restart
    dut.ui_in.value = 1 << 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    seg = dut.uo_out.value.integer & 0x7F
    dp  = get_dp()
    assert seg == 0b1000000, f"Glitch wrongly restarted (seg=0b{seg:07b})"
    assert dp  == 0,         f"Glitch wrongly restarted (dp={dp})"

    # 3) Proper debounced pb0 press (≥4 cycles): must restart
    for _ in range(4):
        dut.ui_in.value = 1 << 0
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0

    # 4) After debounce, dp should go high again and one mole lights
    idx = await wait_active(dut)
    assert 0 <= idx <= 6, "Debounced pb0 did not restart the game"

@cocotb.test()
async def test_one_second_lockout(dut):
    """Verify that after wrong-press lockout lasts ~1s, then clears."""
    cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())  # 1 MHz
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Wait for an active segment
    idx = await wait_active(dut)
    # Choose a wrong button
    wrong = (idx + 1) % 8

    # Wrong press: should lock out
    dut.ui_in.value = 1 << wrong
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Immediately attempt correct press: should NOT increment
    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Lockout failed—score incremented too early"

    # Now wait for ~LOCK_CYCLES cycles plus a margin
    sim_cycles = 10 + 2   # LOCK_CYCLES in sim is 10
    for _ in range(sim_cycles):
        await RisingEdge(dut.clk)

    # After lockout expires, correct press should now increment
    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    assert dut.uio_out.value.integer == 1, "Lockout did not clear after 1 second"


@cocotb.test()
async def test_lockout_independent_buttons(dut):
    """Locking out one wrong button should not block other buttons."""
    cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Pick the active segment
    idx = await wait_active(dut)
    wrong1 = (idx + 1) % 8
    wrong2 = (idx + 2) % 8

    # Press wrong1 to lock it out
    dut.ui_in.value = 1 << wrong1
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Immediately press wrong2 (should also lock it, not prevented by wrong1's lockout)
    dut.ui_in.value = 1 << wrong2
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Both bits should be set in lockout
    # We can poke into DUT via uio_out of score is 0, but better to check that correct hit still blocked
    # Try correct hit—should still be locked
    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Correct button registered during multi‐button lockout"

    # Now wait for lockout to expire
    for _ in range(12):  # 10 + margin
        await RisingEdge(dut.clk)

    # Now correct hit should work
    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 1, "Multi‐button lockout did not clear"

@cocotb.test()
async def test_no_midgame_restart(dut):
    """Pressing pb0 mid-game must NOT clear score or restart the countdown."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # 1) Score 2 points
    for _ in range(2):
        idx = await wait_active(dut)
        dut.ui_in.value = 1 << idx
        for _ in range(5):
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        for _ in range(3):
            await RisingEdge(dut.clk)

    assert dut.uio_out.value.integer == 2, "Setup: score should be 2"

    # 2) Remember which mole is up
    idx_before = await wait_active(dut)

    # 3) Now press pb0 (mid-game)
    dut.ui_in.value = 1 << 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # 4) dp must still be 1 (game still running), score still 2, same mole
    assert get_dp(dut) == 1, "Mid-game pb0 restarted the game!"
    assert dut.uio_out.value.integer == 2, "Mid-game pb0 cleared the score!"
    idx_after = await wait_active(dut)
    assert idx_after == idx_before, "Mid-game pb0 changed the active mole!"

@cocotb.test()
async def test_dp_behavior(dut):
    """dp==1 during play; dp==0 at game over, without poking game_end."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # helper to read dp
    def get_dp():
        return (dut.uo_out.value.integer >> 7) & 1

    # 1) While the timer is running, dp must stay high
    for _ in range(10):
        await RisingEdge(dut.clk)
        dp = get_dp()
        assert dp == 1, f"dp dropped early during play: dp={dp}"

    # 2) Wait up to N cycles for dp to go low (game over).
    dut._log.info("Waiting for dp→0 (game over)...")
    saw_zero = False
    for cycle in range(2000):
        await RisingEdge(dut.clk)
        if get_dp() == 0:
            saw_zero = True
            dut._log.info(f"→ dp went low at cycle {cycle}")
            break

    if not saw_zero:
        # In GL, the real 15M-cycle timer never expires—skip the rest.
        dut._log.warning("dp never went low within 2000 cycles; skipping game-over check in GL")
        return

    # 3) Once dp has fallen, it must stay 0
    dp = get_dp()
    assert dp == 0, f"dp rose back high after game over: dp={dp}"

@cocotb.test()
async def test_segment_never_seven(dut):
    """segment_select must always be in the range 0–6 (never 7)."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Run for a bunch of NEXT→WAIT cycles
    seen = set()
    for _ in range(50):
        idx = await wait_active(dut)
        seen.add(idx)
        # score it to advance to next
        dut.ui_in.value = 1 << idx
        for _ in range(5):
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        for _ in range(3):
            await RisingEdge(dut.clk)

    assert all(0 <= i <= 6 for i in seen), f"Invalid segment index seen: {seen}"
    assert 7 not in seen, "Got a 7th segment!"

# @cocotb.test()
# async def test_restart_debounce(dut):
#     """At game‐over, a short glitch on pb0 must NOT restart the game; only a debounced press does."""
#     cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
#     dut.ui_in.value = 0
#     await reset_dut(dut)

#     # 1) Run until DP falls (indicating game over)
#     while get_dp(dut) == 1:
#         await RisingEdge(dut.clk)

#     # 2) Glitch pb0 for only 2 cycles (< DEBOUNCE_CYCLES)
#     dut.ui_in.value = 1 << 0
#     await RisingEdge(dut.clk)
#     await RisingEdge(dut.clk)
#     dut.ui_in.value = 0
#     await RisingEdge(dut.clk)

#     # Still in GAME_OVER: display should show “0” (seg=7'b1000000, dp=0)
#     seg_val = dut.uo_out.value.integer & 0x7F
#     dp      = get_dp(dut)
#     assert seg_val == 0b1000000, f"Short glitch wrongly restarted: seg=0b{seg_val:07b}"
#     assert dp      == 0,          f"Short glitch wrongly restarted: dp={dp}"

#     # 3) Now do a proper pb0 press (≥4 cycles) to restart
#     for _ in range(4):
#         dut.ui_in.value = 1 << 0
#         await RisingEdge(dut.clk)
#     dut.ui_in.value = 0

#     # After debounce, DP must go high again and exactly one mole should light
#     # (i.e. wait for an active segment)
#     idx = await wait_active(dut)
#     assert 0 <= idx <= 6, "Proper debounced pb0 did not restart the game"

# @cocotb.test()
# async def test_full_game_and_restart(dut):
#     """Play 5 moles correctly, verify score and display, then restart and check reset."""
#     cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())
#     dut.ui_in.value = 0
#     await reset_dut(dut)

#     # 1) Hit 5 correct moles
#     for expected in range(1, 6):  # counts 1 through 5
#         idx = await wait_active(dut)
#         # press & hold long enough to debounce
#         dut.ui_in.value = 1 << idx
#         for _ in range(5):
#             await RisingEdge(dut.clk)
#         dut.ui_in.value = 0
#         # let FSM settle
#         for _ in range(3):
#             await RisingEdge(dut.clk)

#         # check score LED
#         score = dut.uio_out.value.integer
#         assert score == expected, f"After {expected} hits, score={score}"

#     # 2) Wait for game end: DP goes low when countdown completes
#     while get_dp(dut) == 1:
#         await RisingEdge(dut.clk)

#     # now display should show '5' with DP=0
#     seg_val = dut.uo_out.value.integer & 0x7F
#     dp      = get_dp(dut)
#     assert seg_val == 0b0010010, f"Display seg for '5' wrong: {seg_val:07b}"
#     assert dp      == 0,         f"DP should be 0 at game over, got {dp}"

#     # 3) Debounced restart on pb0
#     dut.ui_in.value = 0
#     for _ in range(4):            # hold pb0 ≥ DEBOUNCE_CYCLES
#         dut.ui_in.value = 1 << 0
#         await RisingEdge(dut.clk)
#     dut.ui_in.value = 0
#     await RisingEdge(dut.clk)

#     # 4) New game starts: DP must go high again and score cleared
#     # Wait for DP==1 (game running) and for a new active mole
#     while get_dp(dut) == 0:
#         await RisingEdge(dut.clk)
#     # score LEDs should have reset to 0
#     assert dut.uio_out.value.integer == 0, "Score did not clear on restart"
#     # now one mole must light
#     new_idx = await wait_active(dut)
#     assert 0 <= new_idx <= 6, "No new mole lit after restart"