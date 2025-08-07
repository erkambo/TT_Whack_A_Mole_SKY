<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This tiny ASIC lights up random segments of a 7-segment display and challenges the player to hit the corresponding push-button as fast as possible. Each correct press turns that segment off and scores a point; each incorrect press “locks out” that button for the remainder of the round. A countdown timer limits the game duration, and the final score is shown on the display.

Image
![image](https://github.com/user-attachments/assets/8d61c803-3c48-4858-84d8-b377c431ce2d)


**I/O Signal Assignment**

| Signal Name  | Direction | Width | Description                     |
|--------------|-----------|:-----:|---------------------------------|
| `clk`        | input     | 1     | System clock     |
| `rst_n`      | input     | 1     | Active-low reset                |
| `seg7_a…g`   | output    | 7     | 7-segment cathode/anode lines   |
| `seg7_dp`    | output    | 1     | Decimal point                   |
| `btn[7:0]`   | input     | 8     | Push-button inputs              |
| `led[7:0]`   | output    | 8     | LED mirror of buttons           |
| `score[3:0]` | output    | 4     | Binary score output             |

**Internal Signals**
| Name              | Width | From → To          | Description                             |
|-------------------|:-----:|--------------------|-----------------------------------------|
| `rand_seg[2:0]`   | 3     | RNG → FSM          | Which segment to light next             |
| `countdown[15:0]` | 16    | Timer → FSM        | Remaining game time                     |
| `btn_sync[7:0]`   | 8     | ButtonIF → FSM     | Debounced & synchronized button inputs  |
| `lockout[7:0]`    | 8     | FSM → ButtonIF     | Mask for disabled buttons after error   |
| `score_cnt[7:0]`  | 8     | FSM → ScoreCounter | Current player score                    |
| `state[2:0]`      | 3     | Control FSM regs   | FSM current state (e.g., IDLE, PLAY)    |

## How to test
**1. Unit Tests with Cocotb**
- Test RNG linear-feedback behavior.

- Test timer countdown.

- Test FSM transitions for correct button press, incorrect press (lockout), timer expiration.

**2. On-Hardware Validation**

- Drive the 7-segment display on the TT test board.

- Hook up all 8 push-buttons and LEDs.

- Verify display lighting matches RNG output.

- Time trials: measure reaction-to-light and correct lockout behavior.

- Score read-out on display at end of round.



## External hardware
- Push Buttons

List external hardware used in your project (e.g. PMOD, LED display, etc), if any
