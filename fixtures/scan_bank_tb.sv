// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module scan_bank_tb;
  reg clk_i=0, rst_ni=1, qd_scan_en=0, qd_scan_in=0;
  reg [3:0] d_i=0, expected;
  wire [3:0] q_o, reference_q;
  wire qd_scan_out;
  scanned dut(.*);
  caliptra_prim_generic_flop #(.Width(4), .ResetValue(0)) reference_bank (
    .clk_i, .rst_ni, .d_i, .q_o(reference_q));
  task tick;
    #2; clk_i=1; #2; clk_i=0; #2;
  endtask
  task check_state;
    if (q_o !== expected || qd_scan_out !== expected[3])
      $fatal(1,"scan state mismatch: got %b expected %b",q_o,expected);
  endtask
  initial begin
    #1; rst_ni=0; #1; expected=0; check_state(); rst_ni=1;
    for (integer pattern=0;pattern<16;pattern++) begin
      qd_scan_en=0; d_i=pattern; tick(); expected=pattern; check_state();
      if (q_o !== reference_q) $fatal(1,"normal-mode mismatch");
      qd_scan_en=1;
      for (integer bit_index=3;bit_index>=0;bit_index--) begin
        qd_scan_in=(pattern>>bit_index)&1;
        expected={expected[2:0],qd_scan_in}; tick(); check_state();
      end
    end
    // Four-state serial data and asynchronous reset during shift.
    qd_scan_in=1'bx;
    repeat (4) begin expected={expected[2:0],qd_scan_in}; tick(); check_state(); end
    rst_ni=0; #1; expected=0; check_state();
    rst_ni=1; qd_scan_en=0; d_i=4'b1010; tick(); expected=d_i; check_state();
    if(q_o !== reference_q) $fatal(1,"post-reset normal-mode mismatch");
    $display("PASS: 16 capture/shift patterns, X propagation and asynchronous reset");
    $finish;
  end
endmodule
