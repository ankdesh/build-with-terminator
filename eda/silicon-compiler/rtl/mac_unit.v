module mac_unit #(
    parameter WIDTH = 16,
    parameter ACC_WIDTH = 40
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 valid_i,
    input  wire [WIDTH-1:0]     a_i,
    input  wire [WIDTH-1:0]     b_i,
    output reg                  valid_o,
    output reg  [ACC_WIDTH-1:0] acc_o
);
    wire [2*WIDTH-1:0] product;
    wire [ACC_WIDTH-1:0] product_ext;

    assign product = a_i * b_i;
    assign product_ext = {{(ACC_WIDTH-(2*WIDTH)){1'b0}}, product};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc_o <= {ACC_WIDTH{1'b0}};
            valid_o <= 1'b0;
        end else begin
            valid_o <= valid_i;
            if (clear) begin
                acc_o <= {ACC_WIDTH{1'b0}};
            end else if (valid_i) begin
                acc_o <= acc_o + product_ext;
            end
        end
    end
endmodule

