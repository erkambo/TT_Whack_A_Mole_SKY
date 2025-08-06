`default_nettype none

//-----------------------------------------------------------------------------  
// Button debouncer module  
//-----------------------------------------------------------------------------  
module button_debouncer #(  
    parameter DEBOUNCE_CYCLES = 4  // Number of cycles button must be stable  
)(  
    input  wire clk,  
    input  wire rst_n,  
    input  wire btn_in,    // Raw button input  
    output reg  btn_out    // Debounced output  
);  
    reg [DEBOUNCE_CYCLES-1:0] shift;  
    always @(posedge clk or negedge rst_n) begin  
        if (!rst_n) begin  
            shift   <= {DEBOUNCE_CYCLES{1'b0}};  
            btn_out <= 1'b0;  
        end else begin  
            shift <= {shift[DEBOUNCE_CYCLES-2:0], btn_in};  
            if (&shift)        // All 1's = stable press  
                btn_out <= 1'b1;  
            else if (~|shift)  // All 0's = stable release  
                btn_out <= 1'b0;  
        end  
    end  
endmodule  

//-----------------------------------------------------------------------------  
// LFSR for segment selection  
//-----------------------------------------------------------------------------  
module rng_lfsr(  
    input  wire       clk,  
    input  wire       rst_n,  
    output reg [2:0]  rand_seg  
);  
    reg [15:0] lfsr;  
    wire feedback = lfsr[0] ^ lfsr[2];  
    always @(posedge clk or negedge rst_n) begin  
        if (!rst_n)  
            lfsr <= 16'hACE1;  
        else  
            lfsr <= {lfsr[14:0], feedback};  
    end  
    always @(posedge clk or negedge rst_n) begin  
        if (!rst_n)  
            rand_seg <= 3'd0;  
        else  
            rand_seg <= lfsr[2:0];  
    end  
endmodule  

//-----------------------------------------------------------------------------  
// 7-segment display driver  
//-----------------------------------------------------------------------------  
module seg7_driver(  
    input  wire [2:0]  segment_select,  
    input  wire        game_end,  
    input  wire [7:0]  score,  
    output reg  [6:0]  seg,  
    output reg         dp  
);  
    always @(*) begin  
        if (!game_end) begin  
            seg = 7'b1111111;  
            case (segment_select)  
                3'd0: seg[0] = 1'b0;  
                3'd1: seg[1] = 1'b0;  
                3'd2: seg[2] = 1'b0;  
                3'd3: seg[3] = 1'b0;  
                3'd4: seg[4] = 1'b0;  
                3'd5: seg[5] = 1'b0;  
                3'd6: seg[6] = 1'b0;  
                default: seg[0] = 1'b0;  
            endcase  
            dp = 1'b1;  
        end else begin  
            case (score[3:0])  
                4'h0: seg = 7'b1000000;  
                4'h1: seg = 7'b1111001;  
                4'h2: seg = 7'b0100100;  
                4'h3: seg = 7'b0110000;  
                4'h4: seg = 7'b0011001;  
                4'h5: seg = 7'b0010010;  
                4'h6: seg = 7'b0000010;  
                4'h7: seg = 7'b1111000;  
                4'h8: seg = 7'b0000000;  
                4'h9: seg = 7'b0010000;  
                4'hA: seg = 7'b0001000;  
                4'hB: seg = 7'b0000011;  
                4'hC: seg = 7'b1000110;  
                4'hD: seg = 7'b0100001;  
                4'hE: seg = 7'b0000110;  
                4'hF: seg = 7'b0001110;  
            endcase  
            dp = 1'b0;  
        end  
    end  
endmodule  

//-----------------------------------------------------------------------------  
// Countdown Timer with external start control  
//-----------------------------------------------------------------------------  
module game_timer(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start_btn,   // pb0
    output reg        game_end
);
    reg [24:0] count;
    reg        prev_start;

    `ifdef SIMULATION
        localparam TARGET_COUNT = 25'd1500;
    `else
        localparam TARGET_COUNT = 25'd15_000_000;
    `endif

    // detect rising edge of start_btn
    wire start_edge = start_btn && !prev_start;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count      <= 25'd0;
            game_end   <= 1'b0;
            prev_start <= 1'b0;
        end else begin
            prev_start <= start_btn;

            if (game_end) begin
                // only when already ended, pressing pb0 restarts
                if (start_edge) begin
                    count    <= 25'd0;
                    game_end <= 1'b0;
                end
            end
            else begin
                // normal countdown
                if (count >= TARGET_COUNT)
                    game_end <= 1'b1;
                else
                    count <= count + 1'b1;
            end
        end
    end
endmodule

//-----------------------------------------------------------------------------  
// Game Control FSM with IDLE, NEXT, WAIT, GAME_OVER and 1s lockout timer  
//-----------------------------------------------------------------------------  
module game_fsm(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [2:0]  rand_seg,
    input  wire [7:0]  btn_sync,
    input  wire        start_btn,   // pb0
    input  wire        game_end,
    output reg  [2:0]  segment_select,
    output reg  [7:0]  lockout,
    output reg  [7:0]  score_cnt
);
    typedef enum reg [1:0] { IDLE, NEXT, WAIT, GAME_OVER } state_t;
    state_t state;

    // edge detect on start_btn
    reg prev_start;
    wire start_edge = start_btn && !prev_start;

    // 1-second lockout counter
    reg [19:0] lock_timer;
    `ifdef SIMULATION
        localparam LOCK_CYCLES = 20'd10;
    `else
        localparam LOCK_CYCLES = 20'd1000000;
    `endif

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= NEXT;       // auto-start on reset
            prev_start      <= 1'b0;
            lockout         <= 8'd0;
            score_cnt       <= 8'd0;
            segment_select  <= 3'd0;
            lock_timer      <= 20'd0;
        end else begin
            prev_start <= start_btn;

            case (state)
            IDLE: begin
                if (start_edge) begin
                    score_cnt      <= 8'd0;
                    lockout        <= 8'd0;
                    segment_select <= 3'd0;
                    lock_timer     <= 20'd0;
                    state          <= NEXT;
                end
            end

            NEXT: begin
                segment_select <= (rand_seg == 3'd7) ? 3'd0 : rand_seg;
                lockout        <= 8'd0;
                lock_timer     <= 20'd0;
                state          <= WAIT;
            end

            WAIT: begin
                // penalty countdown
                if (lock_timer != 20'd0) begin
                    lock_timer <= lock_timer - 1;
                    if (lock_timer == 20'd1)
                        lockout <= 8'd0;
                end

                if (game_end) begin
                    state <= GAME_OVER;
                end
                else if (btn_sync[segment_select]) begin
                    // correct hit
                    score_cnt <= score_cnt + 1;
                    state     <= NEXT;
                end
                else if (|btn_sync && lock_timer == 20'd0) begin
                    // wrong hit, start a 1s lockout (only if none already running)
                    lockout    <= btn_sync;
                    lock_timer <= LOCK_CYCLES;
                end
                // ** no mid-game start_btn handling here **
            end

            GAME_OVER: begin
                lockout <= 8'hFF;   // lock all buttons
                if (start_edge) begin
                    // only now does pb0 restart
                    score_cnt      <= 8'd0;
                    lockout        <= 8'd0;
                    segment_select <= 3'd0;
                    lock_timer     <= 20'd0;
                    state          <= NEXT;
                end
            end
            endcase
        end
    end
endmodule 

//-----------------------------------------------------------------------------  
// Top-level: tt_um_whack_a_mole with original ports (uio_in, ena)  
//-----------------------------------------------------------------------------  
module tt_um_whack_a_mole(  
    input  wire [7:0] ui_in,  
    output wire [7:0] uo_out,  
    input  wire [7:0] uio_in,  
    output wire [7:0] uio_out,  
    output wire [7:0] uio_oe,  
    input  wire       ena,  
    input  wire       clk,  
    input  wire       rst_n  
);  
    wire [7:0] deb_btn;  
    genvar i;  
    generate  
        for (i=0; i<8; i=i+1) begin : btn_deb  
            button_debouncer #(.DEBOUNCE_CYCLES(4)) db (  
                .clk    (clk),  
                .rst_n  (rst_n),  
                .btn_in (ui_in[i]),  
                .btn_out(deb_btn[i])  
            );  
        end  
    endgenerate  
    wire start_btn = deb_btn[0];  
    wire       game_end;  
    wire [2:0] rand_seg;  
    wire [7:0] btn_sync;  
    wire [2:0] segment_select;  
    wire [7:0] lockout;  
    wire [7:0] score;  
    wire [6:0] seg;  
    wire       dp;  
    game_timer timer_inst (  
        .clk       (clk),  
        .rst_n     (rst_n),  
        .start_btn(start_btn),  
        .game_end (game_end)  
    );  
    rng_lfsr rng_inst (  
        .clk     (clk),  
        .rst_n   (rst_n),  
        .rand_seg(rand_seg)  
    );  
    game_fsm fsm_inst (  
        .clk            (clk),  
        .rst_n          (rst_n),  
        .rand_seg       (rand_seg),  
        .btn_sync       (btn_sync),  
        .start_btn      (start_btn),  
        .game_end       (game_end),  
        .segment_select (segment_select),  
        .lockout        (lockout),  
        .score_cnt      (score)  
    );  
    assign btn_sync = deb_btn & ~lockout;  
    seg7_driver drv_inst (  
        .segment_select(segment_select),  
        .game_end      (game_end),  
        .score         (score),  
        .seg           (seg),  
        .dp            (dp)  
    );  
    assign uo_out  = {dp, seg};  
    assign uio_out = score;  
    assign uio_oe  = 8'hFF;  
    wire _unused = &{ena, uio_in};  
endmodule  

`default_nettype wire
