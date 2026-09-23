(* blackbox *) module SDFF(input SI, output SO, input SE, CK, RN); endmodule
module top(input test_mode, input scan_in, output scan_out, input clock, reset);
  wire middle;
  SDFF u0(.SI(scan_in), .SO(middle), .SE(test_mode), .CK(clock), .RN(reset));
  SDFF u1(.SI(middle), .SO(scan_out), .SE(test_mode), .CK(clock), .RN(reset));
endmodule
