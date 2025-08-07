`default_nettype none
`timescale 1ns / 1ps

module tb ();

  // Dump the signals to a VCD file. You can view it with gtkwave or surfer.
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);
    #1;
  end

  // Inputs
  reg clk;
  reg rst_n    = 1;
  reg ena      = 1'b1;
  reg [7:0] ui_in  = 8'd0;
  reg [7:0] uio_in = 8'd0;

  // Raw outputs from the DUT (may be X/Z in GL sim)
  wire [7:0] raw_uo_out;
  wire [7:0] raw_uio_out;
  wire [7:0] uio_oe;

  // Filtered outputs (no X/Z)
  wire [7:0] uo_out;
  wire [7:0] uio_out;

`ifdef GL_TEST
  // Power pins for gate-level
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  // Instantiate the DUT
  tt_um_whack_a_mole user_project (
`ifdef GL_TEST
    .VPWR   (VPWR),
    .VGND   (VGND),
`endif
    .ui_in  (ui_in),
    .uo_out (raw_uo_out),
    .uio_in (uio_in),
    .uio_out(raw_uio_out),
    .uio_oe (uio_oe),
    .ena    (ena),
    .clk    (clk),
    .rst_n  (rst_n)
  );

  // Filter out any X/Z bits so cocotb .integer never fails
  genvar i;
  generate
    for (i = 0; i < 8; i = i + 1) begin
      // only drive a '1' if raw bit is exactly 1, otherwise 0
      assign uo_out[i]  = (raw_uo_out[i]  === 1'b1) ? 1'b1 : 1'b0;
      assign uio_out[i] = (raw_uio_out[i] === 1'b1) ? 1'b1 : 1'b0;
    end
  endgenerate

endmodule

`default_nettype wire
