// ha_silicon_fuse_otp.sv — spec stub for future silicon OTP apoptosis bit.
// Not synthesizable product claim. Sim-facing contract mirror of C eFUSE.
// TABU: treat this file as MEASURED silicon signoff.
`timescale 1ns/1ps
module ha_silicon_fuse_otp (
    input  wire clk,
    input  wire blow_req,
    input  wire [31:0] lie_score_milli,
    output reg  blown,
    output reg  [31:0] blow_count,
    output wire current_gate   // 1 = current may flow, 0 = apoptosis blocks
);
  // Irreversible latch — once blown, stays blown (no clear port).
  assign current_gate = ~blown;
  initial begin
    blown = 1'b0;
    blow_count = 32'd0;
  end
  always @(posedge clk) begin
    if (blow_req && !blown) begin
      blown <= 1'b1;
      blow_count <= blow_count + 32'd1;
    end else if (blow_req && blown) begin
      blow_count <= blow_count + 32'd1; // re-blow counts; bit stays 1
    end
  end
endmodule
