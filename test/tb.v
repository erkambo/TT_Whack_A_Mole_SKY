`default_nettype none
`timescale 1ns / 1ps

// Cocotb-driven testbench for tt_um_whack_a_mole
module tb();

  // Waveform dump
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);
  end

  // Clock: 1 MHz (1000ns period)
  reg clk = 0;
  initial forever begin
    #500 clk = ~clk;  // Half period = 500ns
  end

  // DUT inputs: let cocotb manage reset and stimulus
  reg rst_n = 1;
  reg [7:0] ui_in = 8'd0;    // Dedicated inputs (buttons)
  reg [7:0] uio_in = 8'd0;   // IOs: Input path
  reg ena = 1'b1;            // Enable signal

  // DUT outputs
  wire [7:0] uo_out;         // Dedicated outputs (7-segment display)
  wire [7:0] uio_out;        // IOs: Output path (score LEDs)
  wire [7:0] uio_oe;         // IOs: Enable path

  // Instantiate the tt_um_whack_a_mole
  tt_um_whack_a_mole dut (
    .ui_in      (ui_in),
    .uo_out     (uo_out),
    .uio_in     (uio_in),
    .uio_out    (uio_out),
    .uio_oe     (uio_oe),
    .ena        (ena),
    .clk        (clk),
    .rst_n      (rst_n)
  );

endmodule
