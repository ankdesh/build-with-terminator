#!/usr/bin/env python3
"""
diagram_generator.py
Generates high-resolution Hardware Microarchitecture Diagrams, Hardware Waveforms,
Hardware Handshake Sequence Flowcharts, and Control State Machine Diagrams
for all 4 performance modeling examples (Examples 0, 1, 2, and 3).
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

OUTPUT_DIR = "generated_diagrams"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
# EXAMPLE 1: PIPELINED ALU DIAGRAMS
# =============================================================================

def generate_ex1_diagrams():
    # 1. Architecture Diagram
    fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC'); ax.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Pipelined ALU Hardware Microarchitecture Specification", fontsize=13, fontweight='bold', ha='center', color='#0F172A')

    cpu_box = patches.FancyBboxPatch((3, 14), 23, 32, boxstyle="round,pad=0.5", ec="#1E293B", fc="#E2E8F0", lw=2)
    ax.add_patch(cpu_box)
    ax.text(14.5, 41, "Initiator Core / CPU\n(Master)", fontsize=10, fontweight='bold', ha='center', color='#1E293B')
    ax.text(14.5, 27, "• Request Generator\n• Operands (A, B)\n• Operation Code\n• Handshake Control", fontsize=8, ha='center', color='#334155')

    ax.annotate("", xy=(36, 36), xytext=(26, 36), arrowprops=dict(arrowstyle="->", lw=2, color="#0EA5E9"))
    ax.text(31, 38, "req_valid, op_code,\noperand_a, operand_b", fontsize=7.5, fontweight='bold', ha='center', color="#0369A1")

    ax.annotate("", xy=(26, 24), xytext=(36, 24), arrowprops=dict(arrowstyle="->", lw=2, color="#D97706"))
    ax.text(31, 20, "req_ready (1 cycle ack)", fontsize=7.5, fontweight='bold', ha='center', color="#92400E")

    alu_box = patches.FancyBboxPatch((36, 4), 61, 48, boxstyle="round,pad=0.5", ec="#0F172A", fc="#FFFFFF", lw=2)
    ax.add_patch(alu_box)
    ax.text(66.5, 48.5, "Pipelined ALU Core (Slave)", fontsize=11, fontweight='bold', ha='center', color='#0F172A')

    input_reg = patches.FancyBboxPatch((40, 31), 14, 12, boxstyle="round,pad=0.3", ec="#D97706", fc="#FEF3C7", lw=1.5)
    ax.add_patch(input_reg)
    ax.text(47, 39, "Input Register\nStage", fontsize=8, fontweight='bold', ha='center', color="#92400E")
    ax.text(47, 33, "(1 Cycle Ack)", fontsize=7, ha='center', color="#B45309")

    dispatch_box = patches.FancyBboxPatch((58, 31), 14, 12, boxstyle="round,pad=0.3", ec="#0284C7", fc="#E0F2FE", lw=1.5)
    ax.add_patch(dispatch_box)
    ax.text(65, 39, "Dispatch &\nControl Unit", fontsize=8, fontweight='bold', ha='center', color="#075985")
    ax.text(65, 33, "(Op Decoder)", fontsize=7, ha='center', color="#0369A1")

    add_box = patches.FancyBboxPatch((76, 37), 18, 7, boxstyle="round,pad=0.2", ec="#16A34A", fc="#DCFCE7", lw=1.5)
    ax.add_patch(add_box)
    ax.text(85, 40.5, "3-Cycle Adder Unit", fontsize=8, fontweight='bold', ha='center', color="#166534")

    mul_box = patches.FancyBboxPatch((76, 26), 18, 7, boxstyle="round,pad=0.2", ec="#9333EA", fc="#F3E8FF", lw=1.5)
    ax.add_patch(mul_box)
    ax.text(85, 29.5, "4-Cycle Multiplier Unit", fontsize=8, fontweight='bold', ha='center', color="#6B21A8")

    rob_box = patches.FancyBboxPatch((40, 8), 54, 15, boxstyle="round,pad=0.4", ec="#DC2626", fc="#FEE2E2", lw=1.5)
    ax.add_patch(rob_box)
    ax.text(67, 18, "In-Order Reorder Buffer (ROB) & Retirement FIFO", fontsize=9, fontweight='bold', ha='center', color="#991B1B")
    ax.text(67, 11.5, "Holds completed out-of-order results until older operations retire", fontsize=7.5, ha='center', color="#7F1D1D")

    ax.annotate("", xy=(58, 37), xytext=(54, 37), arrowprops=dict(arrowstyle="->", lw=1.5, color="#64748B"))
    ax.annotate("", xy=(76, 40.5), xytext=(72, 40.5), arrowprops=dict(arrowstyle="->", lw=1.5, color="#16A34A"))
    ax.annotate("", xy=(76, 29.5), xytext=(72, 29.5), arrowprops=dict(arrowstyle="->", lw=1.5, color="#9333EA"))
    ax.annotate("", xy=(67, 23), xytext=(67, 31), arrowprops=dict(arrowstyle="->", lw=1.5, color="#DC2626"))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "alu_architecture_block_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 2. Timing Diagram
    fig, axes = plt.subplots(7, 1, figsize=(11, 7.5), sharex=True, dpi=300)
    fig.patch.set_facecolor('#F8FAFC')
    
    clk_x, clk_y = [], []
    for c in range(8):
        clk_x.extend([c, c+0.5, c+0.5, c+1]); clk_y.extend([0, 0, 1, 1])
    axes[0].step(clk_x, clk_y, where='post', color='#0F172A', lw=1.5)
    axes[0].set_ylabel("clk", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[0].set_ylim(-0.2, 1.2); axes[0].set_yticks([])

    vld_x = [0, 1, 4, 4, 8]; vld_y = [0, 1, 1, 0, 0]
    axes[1].step(vld_x, vld_y, where='post', color='#0EA5E9', lw=1.8)
    axes[1].set_ylabel("req_valid", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[1].set_ylim(-0.2, 1.2); axes[1].set_yticks([])

    rdy_x = [0, 1, 1, 2, 2, 3, 3, 4, 4, 8]; rdy_y = [0, 1, 0, 1, 0, 1, 0, 0, 0, 0]
    axes[2].step(rdy_x, rdy_y, where='post', color='#D97706', lw=1.8)
    axes[2].set_ylabel("req_ready", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[2].set_ylim(-0.2, 1.2); axes[2].set_yticks([])

    occ_x = [0, 1, 2, 2, 3, 3, 4, 4, 8]; occ_y = [0, 1, 0, 1, 0, 1, 0, 0, 0]
    axes[3].step(occ_x, occ_y, where='post', color='#CA8A04', lw=1.8)
    axes[3].set_ylabel("input_stage", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[3].set_ylim(-0.2, 1.2); axes[3].set_yticks([])

    depth_x = [0, 1, 2, 3, 4, 6, 7, 8]; depth_y = [0, 1, 2, 3, 2, 0, 0, 0]
    axes[4].step(depth_x, depth_y, where='post', color='#16A34A', lw=1.8)
    axes[4].set_ylabel("pipe_depth", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[4].set_ylim(-0.5, 3.5); axes[4].set_yticks([0, 1, 2, 3])

    op_times = [(0, 1, "IDLE", "#94A3B8"), (1, 2, "ADD", "#16A34A"), (2, 4, "MIXED", "#EA580C"), (4, 6, "MIXED", "#EA580C"), (6, 8, "IDLE", "#94A3B8")]
    for t1, t2, label, color in op_times:
        axes[5].plot([t1, t2], [0.5, 0.5], color=color, lw=12, solid_capstyle='butt')
        axes[5].text((t1 + t2)/2, 0.5, label, ha='center', va='center', color='white', fontweight='bold', fontsize=8)
    axes[5].set_ylabel("active_op", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[5].set_ylim(0, 1); axes[5].set_yticks([])

    ret_times = [(0, 4, "NONE", "#94A3B8"), (4, 5, "Tx 0", "#2563EB"), (5, 6, "NONE", "#94A3B8"), (6, 7, "Tx 1 & 2", "#9333EA"), (7, 8, "NONE", "#94A3B8")]
    for t1, t2, label, color in ret_times:
        axes[6].plot([t1, t2], [0.5, 0.5], color=color, lw=12, solid_capstyle='butt')
        axes[6].text((t1 + t2)/2, 0.5, label, ha='center', va='center', color='white', fontweight='bold', fontsize=8)
    axes[6].set_ylabel("retired_tx", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[6].set_ylim(0, 1); axes[6].set_yticks([])

    for ax in axes:
        ax.set_facecolor('#F1F5F9')
        for c in range(9): ax.axvline(c, color='#CBD5E1', linestyle='--', lw=0.8)

    axes[6].set_xlabel("Hardware Time (Clock Cycles, 1 cycle = 10ns @ 100MHz)", fontweight='bold', fontsize=10, color='#0F172A')
    axes[6].set_xticks(range(9))
    axes[6].set_xticklabels([f"cy {c}" for c in range(9)])

    fig.suptitle("Pipelined ALU Cycle-Accurate Hardware Timing Waveforms", fontsize=13, fontweight='bold', color='#0F172A')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "alu_timing_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 3. Sequence Diagram
    fig, ax = plt.subplots(figsize=(9.2, 6.2), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Hardware Valid/Ready Handshake & Pipeline Execution Flow", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    lifelines = [(20, "Initiator Core"), (45, "Input Reg Stage"), (70, "Execution Pipeline"), (90, "Reorder Buffer (ROB)")]
    for x, label in lifelines:
        ax.plot([x, x], [10, 50], color="#94A3B8", linestyle="--", lw=1.5)
        ax.text(x, 52, label, fontsize=9, fontweight='bold', ha='center', color="#0F172A", bbox=dict(boxstyle="square,pad=0.3", fc="#E2E8F0", ec="#64748B", lw=1))

    messages = [
        (20, 45, 45, "1. Assert req_valid, op_code, operands A/B", "#0284C7", "solid"),
        (45, 20, 40, "2. Assert req_ready (1 cycle ack delay)", "#D97706", "dashed"),
        (45, 70, 35, "3. Dispatch to ADD (3cy) or MUL (4cy) pipeline", "#2563EB", "solid"),
        (70, 90, 25, "4. Compute finished -> Push result to ROB slot", "#16A34A", "solid"),
        (90, 90, 15, "5. ROB Head Check -> Assert out_valid & Retire", "#9333EA", "solid")
    ]
    for x1, x2, y, text, color, style in messages:
        ls = "-" if style == "solid" else "--"
        if x1 != x2:
            ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle="->", lw=1.8, color=color, linestyle=ls))
            ax.text((x1 + x2)/2, y + 1.5, text, fontsize=8, fontweight='bold', ha='center', color=color)
        else:
            ax.text(x1 + 1, y, text, fontsize=8, fontweight='bold', ha='left', color=color)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "alu_sequence_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 4. State Machine Diagram
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 36, "Hardware Pipeline Control State Machine", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    states = [
        (10, 20, "1. IDLE\n(Wait valid)", "#3B82F6"),
        (32, 20, "2. REQ_ACK\n(Pulse ready 1cy)", "#D97706"),
        (54, 20, "3. EXECUTE\n(3cy ADD / 4cy MUL)", "#0284C7"),
        (76, 20, "4. ROB_STALL\n(Wait ROB Head)", "#16A34A"),
        (92, 20, "5. RETIRE\n(Assert out_valid)", "#9333EA")
    ]
    for x, y, label, color in states:
        box = patches.FancyBboxPatch((x-6, y-6), 12, 12, boxstyle="circle,pad=0.3", ec=color, fc="#FFFFFF", lw=2)
        ax.add_patch(box)
        ax.text(x, y, label, fontsize=7, fontweight='bold', ha='center', va='center', color=color)

    arrows = [(16, 26), (38, 48), (60, 70), (82, 86)]
    for x1, x2 in arrows:
        ax.annotate("", xy=(x2, 20), xytext=(x1, 20), arrowprops=dict(arrowstyle="->", lw=1.8, color="#64748B"))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "alu_pipeline_states.png"), dpi=300, bbox_inches='tight')
    plt.close()


# =============================================================================
# EXAMPLE 0: SIMPLE PIPELINE STAGE DIAGRAMS
# =============================================================================

def generate_ex0_diagrams():
    # 1. Architecture Diagram
    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC'); ax.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Simple 3-Stage Pipeline Hardware Architecture (A -> B -> C)", fontsize=13, fontweight='bold', ha='center', color='#0F172A')

    box_a = patches.FancyBboxPatch((3, 15), 22, 30, boxstyle="round,pad=0.5", ec="#1E293B", fc="#E2E8F0", lw=2)
    ax.add_patch(box_a)
    ax.text(14, 38, "Component A\n(Initiator Core)", fontsize=10, fontweight='bold', ha='center', color='#1E293B')
    ax.text(14, 25, "• Stimulus Source\n• Drives Tx Data", fontsize=8, ha='center', color='#334155')

    ax.annotate("", xy=(34, 33), xytext=(25, 33), arrowprops=dict(arrowstyle="->", lw=2, color="#0EA5E9"))
    ax.text(29.5, 36, "A_to_B_valid", fontsize=7.5, fontweight='bold', ha='center', color="#0369A1")
    ax.annotate("", xy=(25, 23), xytext=(34, 23), arrowprops=dict(arrowstyle="->", lw=2, color="#D97706"))
    ax.text(29.5, 19, "A_to_B_ready (1cy ack)", fontsize=7.5, fontweight='bold', ha='center', color="#92400E")

    box_b = patches.FancyBboxPatch((34, 8), 32, 44, boxstyle="round,pad=0.5", ec="#0F172A", fc="#FFFFFF", lw=2)
    ax.add_patch(box_b)
    ax.text(50, 47, "Component B (3-Cycle Stage)", fontsize=10, fontweight='bold', ha='center', color='#0F172A')

    b_reg = patches.FancyBboxPatch((37, 28), 12, 10, boxstyle="round,pad=0.2", ec="#D97706", fc="#FEF3C7", lw=1.5)
    ax.add_patch(b_reg)
    ax.text(43, 33, "Input Reg\n(1 cy ack)", fontsize=7.5, fontweight='bold', ha='center', color="#92400E")

    b_pipe = patches.FancyBboxPatch((52, 28), 12, 10, boxstyle="round,pad=0.2", ec="#16A34A", fc="#DCFCE7", lw=1.5)
    ax.add_patch(b_pipe)
    ax.text(58, 33, "3-Cycle Compute\nPipeline Stage", fontsize=7.5, fontweight='bold', ha='center', color="#166534")

    ax.annotate("", xy=(74, 33), xytext=(66, 33), arrowprops=dict(arrowstyle="->", lw=2, color="#0EA5E9"))
    ax.text(70, 36, "B_to_C_valid", fontsize=7.5, fontweight='bold', ha='center', color="#0369A1")
    ax.annotate("", xy=(66, 23), xytext=(74, 23), arrowprops=dict(arrowstyle="->", lw=2, color="#D97706"))
    ax.text(70, 19, "B_to_C_ready (1cy ack)", fontsize=7.5, fontweight='bold', ha='center', color="#92400E")

    box_c = patches.FancyBboxPatch((74, 8), 23, 44, boxstyle="round,pad=0.5", ec="#0F172A", fc="#E0F2FE", lw=2)
    ax.add_patch(box_c)
    ax.text(85.5, 47, "Component C\n(Target Endpoint)", fontsize=10, fontweight='bold', ha='center', color='#075985')
    ax.text(85.5, 27, "• 1-Cycle Ack\n• 1-Cycle Execution\n• Multiply by 2\n• Data Commit", fontsize=8, ha='center', color='#0369A1')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex0_architecture_block_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 2. Timing Diagram
    fig, axes = plt.subplots(6, 1, figsize=(11, 7), sharex=True, dpi=300)
    fig.patch.set_facecolor('#F8FAFC')
    
    clk_x, clk_y = [], []
    for c in range(8):
        clk_x.extend([c, c+0.5, c+0.5, c+1]); clk_y.extend([0, 0, 1, 1])
    axes[0].step(clk_x, clk_y, where='post', color='#0F172A', lw=1.5)
    axes[0].set_ylabel("clk", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[0].set_ylim(-0.2, 1.2); axes[0].set_yticks([])

    vld_a_x = [0, 1, 2, 8]; vld_a_y = [0, 1, 0, 0]
    axes[1].step(vld_a_x, vld_a_y, where='post', color='#0EA5E9', lw=1.8)
    axes[1].set_ylabel("A_to_B_valid", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[1].set_ylim(-0.2, 1.2); axes[1].set_yticks([])

    rdy_b_x = [0, 1, 2, 8]; rdy_b_y = [0, 1, 0, 0]
    axes[2].step(rdy_b_x, rdy_b_y, where='post', color='#D97706', lw=1.8)
    axes[2].set_ylabel("A_to_B_ready", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[2].set_ylim(-0.2, 1.2); axes[2].set_yticks([])

    b_depth_x = [0, 1, 4, 8]; b_depth_y = [0, 1, 0, 0]
    axes[3].step(b_depth_x, b_depth_y, where='post', color='#16A34A', lw=1.8)
    axes[3].set_ylabel("B_pipe_depth", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[3].set_ylim(-0.5, 2.5); axes[3].set_yticks([0, 1, 2])

    vld_b_x = [0, 4, 5, 8]; vld_b_y = [0, 1, 0, 0]
    axes[4].step(vld_b_x, vld_b_y, where='post', color='#2563EB', lw=1.8)
    axes[4].set_ylabel("B_to_C_valid", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[4].set_ylim(-0.2, 1.2); axes[4].set_yticks([])

    c_ret_x = [0, 6, 7, 8]; c_ret_y = [0, 1, 0, 0]
    axes[5].step(c_ret_x, c_ret_y, where='post', color='#9333EA', lw=1.8)
    axes[5].set_ylabel("C_retire", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[5].set_ylim(-0.2, 1.2); axes[5].set_yticks([])

    for ax in axes:
        ax.set_facecolor('#F1F5F9')
        for c in range(9): ax.axvline(c, color='#CBD5E1', linestyle='--', lw=0.8)

    axes[5].set_xlabel("Hardware Time (Clock Cycles, Total Path Latency = 5 Cycles)", fontweight='bold', fontsize=10, color='#0F172A')
    axes[5].set_xticks(range(9))
    axes[5].set_xticklabels([f"cy {c}" for c in range(9)])

    fig.suptitle("Example 0: 3-Stage Pipeline Timing Waveforms (Scenario 1)", fontsize=13, fontweight='bold', color='#0F172A')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex0_timing_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 3. Sequence Diagram
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Pipeline Stage A -> B -> C Sequence Flow", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    lifelines = [(20, "Initiator A"), (50, "Pipelined Stage B"), (80, "Endpoint C")]
    for x, label in lifelines:
        ax.plot([x, x], [10, 50], color="#94A3B8", linestyle="--", lw=1.5)
        ax.text(x, 52, label, fontsize=9, fontweight='bold', ha='center', color="#0F172A", bbox=dict(boxstyle="square,pad=0.3", fc="#E2E8F0", ec="#64748B", lw=1))

    messages = [
        (20, 50, 45, "1. A_to_B_valid (cy 1)", "#0284C7", "solid"),
        (50, 20, 40, "2. A_to_B_ready ack (cy 2)", "#D97706", "dashed"),
        (50, 50, 32, "3. 3-Cycle Pipeline Exec (cy 1 to 4)", "#16A34A", "solid"),
        (50, 80, 24, "4. B_to_C_valid (cy 4)", "#2563EB", "solid"),
        (80, 50, 18, "5. B_to_C_ready ack (cy 5)", "#D97706", "dashed"),
        (80, 80, 12, "6. Endpoint Compute & Retire (cy 6)", "#9333EA", "solid")
    ]
    for x1, x2, y, text, color, style in messages:
        ls = "-" if style == "solid" else "--"
        if x1 != x2:
            ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle="->", lw=1.8, color=color, linestyle=ls))
            ax.text((x1 + x2)/2, y + 1.5, text, fontsize=8, fontweight='bold', ha='center', color=color)
        else:
            ax.text(x1 + 1, y, text, fontsize=8, fontweight='bold', ha='left', color=color)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex0_sequence_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 4. State Machine Diagram
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 36, "3-Stage Pipeline Control State Machine", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    states = [
        (10, 20, "1. A_SEND\n(cy 1)", "#3B82F6"),
        (32, 20, "2. B_ACK\n(cy 2)", "#D97706"),
        (54, 20, "3. B_EXEC\n(3 cycles)", "#0284C7"),
        (76, 20, "4. C_ACK\n(cy 5)", "#16A34A"),
        (92, 20, "5. RETIRE\n(cy 6)", "#9333EA")
    ]
    for x, y, label, color in states:
        box = patches.FancyBboxPatch((x-6, y-6), 12, 12, boxstyle="circle,pad=0.3", ec=color, fc="#FFFFFF", lw=2)
        ax.add_patch(box)
        ax.text(x, y, label, fontsize=7, fontweight='bold', ha='center', va='center', color=color)

    arrows = [(16, 26), (38, 48), (60, 70), (82, 86)]
    for x1, x2 in arrows:
        ax.annotate("", xy=(x2, 20), xytext=(x1, 20), arrowprops=dict(arrowstyle="->", lw=1.8, color="#64748B"))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex0_pipeline_states.png"), dpi=300, bbox_inches='tight')
    plt.close()


# =============================================================================
# EXAMPLE 2: INTERBLOCK STREAMING FIFO WITH BACKPRESSURE DIAGRAMS
# =============================================================================

def generate_ex2_diagrams():
    # 1. Architecture Diagram
    fig, ax = plt.subplots(figsize=(10.5, 6.0), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC'); ax.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Streaming FIFO Interconnect Hardware Microarchitecture (Backpressure)", fontsize=13, fontweight='bold', ha='center', color='#0F172A')

    box_p = patches.FancyBboxPatch((3, 14), 22, 32, boxstyle="round,pad=0.5", ec="#1E293B", fc="#E2E8F0", lw=2)
    ax.add_patch(box_p)
    ax.text(14, 40, "Producer Core\n(Master Source)", fontsize=10, fontweight='bold', ha='center', color='#1E293B')
    ax.text(14, 25, "• Bursty Stream Writer\n• Stalls when\n  p2f_ready is Low", fontsize=8, ha='center', color='#334155')

    ax.annotate("", xy=(34, 34), xytext=(25, 34), arrowprops=dict(arrowstyle="->", lw=2, color="#0EA5E9"))
    ax.text(29.5, 37, "p2f_valid", fontsize=7.5, fontweight='bold', ha='center', color="#0369A1")
    ax.annotate("", xy=(25, 22), xytext=(34, 22), arrowprops=dict(arrowstyle="->", lw=2, color="#DC2626"))
    ax.text(29.5, 17, "p2f_ready (Stalls Low\nwhen FIFO is FULL)", fontsize=7.5, fontweight='bold', ha='center', color="#991B1B")

    box_f = patches.FancyBboxPatch((34, 8), 34, 44, boxstyle="round,pad=0.5", ec="#0F172A", fc="#FFFFFF", lw=2)
    ax.add_patch(box_f)
    ax.text(51, 47, "Streaming FIFO Unit (Cap = 4)", fontsize=10, fontweight='bold', ha='center', color='#0F172A')

    f_queue = patches.FancyBboxPatch((37, 26), 28, 12, boxstyle="round,pad=0.3", ec="#0284C7", fc="#E0F2FE", lw=1.5)
    ax.add_patch(f_queue)
    ax.text(51, 34, "4-Entry Queue Storage Buffer", fontsize=8, fontweight='bold', ha='center', color="#075985")
    ax.text(51, 28.5, "[ Slot 0 | Slot 1 | Slot 2 | Slot 3 ]", fontsize=7.5, ha='center', color="#0369A1")

    f_ctrl = patches.FancyBboxPatch((37, 11), 28, 11, boxstyle="round,pad=0.3", ec="#D97706", fc="#FEF3C7", lw=1.5)
    ax.add_patch(f_ctrl)
    ax.text(51, 18, "Flow Control & Backpressure Logic", fontsize=8, fontweight='bold', ha='center', color="#92400E")
    ax.text(51, 13, "Deasserts p2f_ready when Size == 4", fontsize=7, ha='center', color="#B45309")

    ax.annotate("", xy=(76, 34), xytext=(68, 34), arrowprops=dict(arrowstyle="->", lw=2, color="#0EA5E9"))
    ax.text(72, 37, "f2c_valid", fontsize=7.5, fontweight='bold', ha='center', color="#0369A1")
    ax.annotate("", xy=(68, 22), xytext=(76, 22), arrowprops=dict(arrowstyle="->", lw=2, color="#DC2626"))
    ax.text(72, 17, "f2c_ready (Stalls Low\nwhen Consumer Busy)", fontsize=7.5, fontweight='bold', ha='center', color="#991B1B")

    box_c = patches.FancyBboxPatch((76, 8), 21, 44, boxstyle="round,pad=0.5", ec="#0F172A", fc="#F0FDF4", lw=2)
    ax.add_patch(box_c)
    ax.text(86.5, 47, "Consumer Core\n(Processing Sink)", fontsize=10, fontweight='bold', ha='center', color='#166534')
    ax.text(86.5, 25, "• Processing Engine\n• Deasserts ready\n  when busy\n• Drains FIFO", fontsize=8, ha='center', color='#15803D')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex2_architecture_block_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 2. Timing Diagram
    fig, axes = plt.subplots(7, 1, figsize=(11, 7.5), sharex=True, dpi=300)
    fig.patch.set_facecolor('#F8FAFC')
    
    clk_x, clk_y = [], []
    for c in range(13):
        clk_x.extend([c, c+0.5, c+0.5, c+1]); clk_y.extend([0, 0, 1, 1])
    axes[0].step(clk_x, clk_y, where='post', color='#0F172A', lw=1.5)
    axes[0].set_ylabel("clk", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[0].set_ylim(-0.2, 1.2); axes[0].set_yticks([])

    p_vld_x = [0, 1, 7, 13]; p_vld_y = [0, 1, 1, 0]
    axes[1].step(p_vld_x, p_vld_y, where='post', color='#0EA5E9', lw=1.8)
    axes[1].set_ylabel("p2f_valid", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[1].set_ylim(-0.2, 1.2); axes[1].set_yticks([])

    p_rdy_x = [0, 1, 5, 10, 13]; p_rdy_y = [0, 1, 0, 1, 1]
    axes[2].step(p_rdy_x, p_rdy_y, where='post', color='#DC2626', lw=1.8)
    axes[2].set_ylabel("p2f_ready", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[2].set_ylim(-0.2, 1.2); axes[2].set_yticks([])

    size_x = [0, 1, 2, 3, 4, 5, 10, 11, 12, 13]; size_y = [0, 1, 2, 3, 4, 4, 3, 2, 1, 0]
    axes[3].step(size_x, size_y, where='post', color='#16A34A', lw=1.8)
    axes[3].set_ylabel("fifo_size", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[3].set_ylim(-0.5, 4.5); axes[3].set_yticks([0, 1, 2, 3, 4])

    p_stall_x = [0, 5, 10, 13]; p_stall_y = [0, 1, 0, 0]
    axes[4].step(p_stall_x, p_stall_y, where='post', color='#D97706', lw=1.8)
    axes[4].set_ylabel("prod_stall", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[4].set_ylim(-0.2, 1.2); axes[4].set_yticks([])

    c_rdy_x = [0, 10, 13]; c_rdy_y = [0, 1, 1]
    axes[5].step(c_rdy_x, c_rdy_y, where='post', color='#0284C7', lw=1.8)
    axes[5].set_ylabel("f2c_ready", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[5].set_ylim(-0.2, 1.2); axes[5].set_yticks([])

    c_stall_x = [0, 1, 10, 13]; c_stall_y = [0, 1, 0, 0]
    axes[6].step(c_stall_x, c_stall_y, where='post', color='#9333EA', lw=1.8)
    axes[6].set_ylabel("cons_stall", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[6].set_ylim(-0.2, 1.2); axes[6].set_yticks([])

    for ax in axes:
        ax.set_facecolor('#F1F5F9')
        for c in range(14): ax.axvline(c, color='#CBD5E1', linestyle='--', lw=0.8)

    axes[6].set_xlabel("Hardware Time (Clock Cycles, FIFO Full at cy 5 -> Producer Stalled until Consumer Starts at cy 10)", fontweight='bold', fontsize=9.5, color='#0F172A')
    axes[6].set_xticks(range(14))
    axes[6].set_xticklabels([f"cy {c}" for c in range(14)])

    fig.suptitle("Example 2: FIFO Backpressure Streaming Waveforms (Scenario 1)", fontsize=13, fontweight='bold', color='#0F172A')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex2_timing_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 3. Sequence Diagram
    fig, ax = plt.subplots(figsize=(9, 5.8), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Backpressure Streaming Flow Control Sequence", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    lifelines = [(20, "Producer Core"), (50, "FIFO Interconnect"), (80, "Consumer Core")]
    for x, label in lifelines:
        ax.plot([x, x], [10, 50], color="#94A3B8", linestyle="--", lw=1.5)
        ax.text(x, 52, label, fontsize=9, fontweight='bold', ha='center', color="#0F172A", bbox=dict(boxstyle="square,pad=0.3", fc="#E2E8F0", ec="#64748B", lw=1))

    messages = [
        (20, 50, 45, "1. p2f_valid burst writes (cy 1 to 4)", "#0284C7", "solid"),
        (50, 20, 39, "2. p2f_ready high (FIFO size < 4)", "#16A34A", "dashed"),
        (50, 20, 32, "3. FIFO FULL (size=4) -> Deassert p2f_ready (cy 5)", "#DC2626", "dashed"),
        (20, 20, 25, "4. Producer STALLED (waiting for ready)", "#D97706", "solid"),
        (80, 50, 18, "5. Consumer starts draining -> f2c_ready high (cy 10)", "#2563EB", "dashed"),
        (50, 20, 12, "6. FIFO size drops -> Assert p2f_ready & Resume Producer", "#9333EA", "dashed")
    ]
    for x1, x2, y, text, color, style in messages:
        ls = "-" if style == "solid" else "--"
        if x1 != x2:
            ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle="->", lw=1.8, color=color, linestyle=ls))
            ax.text((x1 + x2)/2, y + 1.5, text, fontsize=8, fontweight='bold', ha='center', color=color)
        else:
            ax.text(x1 + 1, y, text, fontsize=8, fontweight='bold', ha='left', color=color)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex2_sequence_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 4. State Machine Diagram
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 36, "Streaming FIFO Flow Control State Machine", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    states = [
        (10, 20, "1. NORMAL\n(size < 4)", "#3B82F6"),
        (32, 20, "2. FIFO_FULL\n(p2f_ready Low)", "#DC2626"),
        (54, 20, "3. PROD_STALL\n(Producer waits)", "#D97706"),
        (76, 20, "4. CONS_DRAIN\n(f2c_ready High)", "#16A34A"),
        (92, 20, "5. RESUME\n(p2f_ready High)", "#9333EA")
    ]
    for x, y, label, color in states:
        box = patches.FancyBboxPatch((x-6, y-6), 12, 12, boxstyle="circle,pad=0.3", ec=color, fc="#FFFFFF", lw=2)
        ax.add_patch(box)
        ax.text(x, y, label, fontsize=7, fontweight='bold', ha='center', va='center', color=color)

    arrows = [(16, 26), (38, 48), (60, 70), (82, 86)]
    for x1, x2 in arrows:
        ax.annotate("", xy=(x2, 20), xytext=(x1, 20), arrowprops=dict(arrowstyle="->", lw=1.8, color="#64748B"))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex2_pipeline_states.png"), dpi=300, bbox_inches='tight')
    plt.close()


# =============================================================================
# EXAMPLE 3: SHARED SWITCH ARBITRATION DIAGRAMS
# =============================================================================

def generate_ex3_diagrams():
    # 1. Architecture Diagram
    fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC'); ax.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Shared Switch Crossbar Interconnect Hardware Microarchitecture", fontsize=13, fontweight='bold', ha='center', color='#0F172A')

    for i in range(4):
        y_pos = 42 - i * 11
        box = patches.FancyBboxPatch((3, y_pos), 18, 8, boxstyle="round,pad=0.3", ec="#1E293B", fc="#E2E8F0", lw=1.5)
        ax.add_patch(box)
        ax.text(12, y_pos + 4, f"Initiator Core {i}", fontsize=8, fontweight='bold', ha='center', color='#1E293B')
        ax.annotate("", xy=(30, y_pos + 4), xytext=(21, y_pos + 4), arrowprops=dict(arrowstyle="<->", lw=1.5, color="#0EA5E9"))

    sw_box = patches.FancyBboxPatch((30, 6), 40, 47, boxstyle="round,pad=0.5", ec="#0F172A", fc="#FFFFFF", lw=2)
    ax.add_patch(sw_box)
    ax.text(50, 48, "Shared Crossbar Switch", fontsize=11, fontweight='bold', ha='center', color='#0F172A')

    arb_box = patches.FancyBboxPatch((34, 30), 32, 13, boxstyle="round,pad=0.3", ec="#D97706", fc="#FEF3C7", lw=1.5)
    ax.add_patch(arb_box)
    ax.text(50, 38, "Round-Robin Arbiter", fontsize=8.5, fontweight='bold', ha='center', color="#92400E")
    ax.text(50, 33, "(rr_index = 0..3)", fontsize=7.5, ha='center', color="#B45309")

    lock_box = patches.FancyBboxPatch((34, 11), 32, 13, boxstyle="round,pad=0.3", ec="#0284C7", fc="#E0F2FE", lw=1.5)
    ax.add_patch(lock_box)
    ax.text(50, 19, "Transmission Lock Unit", fontsize=8.5, fontweight='bold', ha='center', color="#075985")
    ax.text(50, 14, "(3-Cycle Busy Duration)", fontsize=7.5, ha='center', color="#0369A1")

    for i in range(4):
        y_pos = 42 - i * 11
        ax.annotate("", xy=(79, y_pos + 4), xytext=(70, y_pos + 4), arrowprops=dict(arrowstyle="->", lw=1.5, color="#16A34A"))
        box = patches.FancyBboxPatch((79, y_pos), 18, 8, boxstyle="round,pad=0.3", ec="#166534", fc="#DCFCE7", lw=1.5)
        ax.add_patch(box)
        ax.text(88, y_pos + 4, f"Target Node {i}", fontsize=8, fontweight='bold', ha='center', color='#166534')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex3_architecture_block_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 2. Timing Diagram
    fig, axes = plt.subplots(6, 1, figsize=(11, 7.5), sharex=True, dpi=300)
    fig.patch.set_facecolor('#F8FAFC')
    
    clk_x, clk_y = [], []
    for c in range(14):
        clk_x.extend([c, c+0.5, c+0.5, c+1]); clk_y.extend([0, 0, 1, 1])
    axes[0].step(clk_x, clk_y, where='post', color='#0F172A', lw=1.5)
    axes[0].set_ylabel("clk", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[0].set_ylim(-0.2, 1.2); axes[0].set_yticks([])

    req_x = [0, 1, 13, 14]; req_y = [0, 1, 1, 0]
    axes[1].step(req_x, req_y, where='post', color='#0EA5E9', lw=1.8)
    axes[1].set_ylabel("req_valid[3:0]", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[1].set_ylim(-0.2, 1.2); axes[1].set_yticks([])

    busy_x = [0, 1, 13, 14]; busy_y = [0, 1, 1, 0]
    axes[2].step(busy_x, busy_y, where='post', color='#DC2626', lw=1.8)
    axes[2].set_ylabel("switch_busy", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[2].set_ylim(-0.2, 1.2); axes[2].set_yticks([])

    rr_times = [(0, 1, "0", "#94A3B8"), (1, 4, "1", "#0284C7"), (4, 7, "2", "#16A34A"), (7, 10, "3", "#D97706"), (10, 13, "0", "#9333EA"), (13, 14, "0", "#94A3B8")]
    for t1, t2, label, color in rr_times:
        axes[3].plot([t1, t2], [0.5, 0.5], color=color, lw=12, solid_capstyle='butt')
        axes[3].text((t1 + t2)/2, 0.5, label, ha='center', va='center', color='white', fontweight='bold', fontsize=8)
    axes[3].set_ylabel("rr_index", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[3].set_ylim(0, 1); axes[3].set_yticks([])

    act_times = [(0, 1, "NONE", "#94A3B8"), (1, 4, "Core 0", "#0284C7"), (4, 7, "Core 1", "#16A34A"), (7, 10, "Core 2", "#D97706"), (10, 13, "Core 3", "#9333EA"), (13, 14, "NONE", "#94A3B8")]
    for t1, t2, label, color in act_times:
        axes[4].plot([t1, t2], [0.5, 0.5], color=color, lw=12, solid_capstyle='butt')
        axes[4].text((t1 + t2)/2, 0.5, label, ha='center', va='center', color='white', fontweight='bold', fontsize=8)
    axes[4].set_ylabel("active_client", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[4].set_ylim(0, 1); axes[4].set_yticks([])

    pend_x = [0, 1, 4, 7, 10, 13, 14]; pend_y = [0, 4, 3, 2, 1, 0, 0]
    axes[5].step(pend_x, pend_y, where='post', color='#EA580C', lw=1.8)
    axes[5].set_ylabel("pending_count", rotation=0, labelpad=30, fontweight='bold', va='center')
    axes[5].set_ylim(-0.5, 4.5); axes[5].set_yticks([0, 1, 2, 3, 4])

    for ax in axes:
        ax.set_facecolor('#F1F5F9')
        for c in range(15): ax.axvline(c, color='#CBD5E1', linestyle='--', lw=0.8)

    axes[5].set_xlabel("Hardware Time (Clock Cycles, 4 Contending Cores Grant Sequentially at cy 1, 4, 7, 10)", fontweight='bold', fontsize=9.5, color='#0F172A')
    axes[5].set_xticks(range(15))
    axes[5].set_xticklabels([f"cy {c}" for c in range(15)])

    fig.suptitle("Example 3: Shared Switch Arbitration Waveforms (Scenario 1)", fontsize=13, fontweight='bold', color='#0F172A')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex3_timing_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 3. Sequence Diagram
    fig, ax = plt.subplots(figsize=(9.2, 5.8), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 56, "Round-Robin Switch Contention Sequence Flow", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    lifelines = [(20, "Initiators (0..3)"), (50, "Switch Arbiter"), (80, "Target Nodes (0..3)")]
    for x, label in lifelines:
        ax.plot([x, x], [10, 50], color="#94A3B8", linestyle="--", lw=1.5)
        ax.text(x, 52, label, fontsize=9, fontweight='bold', ha='center', color="#0F172A", bbox=dict(boxstyle="square,pad=0.3", fc="#E2E8F0", ec="#64748B", lw=1))

    messages = [
        (20, 50, 45, "1. Concurrent req_valid from Cores 0,1,2,3 (cy 1)", "#0284C7", "solid"),
        (50, 20, 39, "2. Arbiter selects Core 0 (rr_index=0) -> Grant Core 0", "#16A34A", "dashed"),
        (50, 80, 32, "3. Forward Core 0 write to Target Node 0", "#2563EB", "solid"),
        (50, 50, 25, "4. Lock Switch for 3 cycles transmission delay", "#DC2626", "solid"),
        (50, 20, 18, "5. Lock expires -> Grant Core 1 (cy 4), Core 2 (cy 7), Core 3 (cy 10)", "#9333EA", "dashed")
    ]
    for x1, x2, y, text, color, style in messages:
        ls = "-" if style == "solid" else "--"
        if x1 != x2:
            ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle="->", lw=1.8, color=color, linestyle=ls))
            ax.text((x1 + x2)/2, y + 1.5, text, fontsize=8, fontweight='bold', ha='center', color=color)
        else:
            ax.text(x1 + 1, y, text, fontsize=8, fontweight='bold', ha='left', color=color)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex3_sequence_diagram.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # 4. State Machine Diagram
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    ax.text(50, 36, "Shared Switch Arbitration Control State Machine", fontsize=13, fontweight='bold', ha='center', color='#0F172A')
    states = [
        (10, 20, "1. IDLE\n(Wait reqs)", "#3B82F6"),
        (32, 20, "2. ARBITRATE\n(Round-Robin)", "#D97706"),
        (54, 20, "3. GRANT\n(Pulse ack)", "#16A34A"),
        (76, 20, "4. SWITCH_BUSY\n(3-Cycle Lock)", "#DC2626"),
        (92, 20, "5. FREE_SWITCH\n(Next client)", "#9333EA")
    ]
    for x, y, label, color in states:
        box = patches.FancyBboxPatch((x-6, y-6), 12, 12, boxstyle="circle,pad=0.3", ec=color, fc="#FFFFFF", lw=2)
        ax.add_patch(box)
        ax.text(x, y, label, fontsize=7, fontweight='bold', ha='center', va='center', color=color)

    arrows = [(16, 26), (38, 48), (60, 70), (82, 86)]
    for x1, x2 in arrows:
        ax.annotate("", xy=(x2, 20), xytext=(x1, 20), arrowprops=dict(arrowstyle="->", lw=1.8, color="#64748B"))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ex3_pipeline_states.png"), dpi=300, bbox_inches='tight')
    plt.close()


if __name__ == "__main__":
    generate_ex1_diagrams()
    generate_ex0_diagrams()
    generate_ex2_diagrams()
    generate_ex3_diagrams()
    print("All 16 diagrams for Examples 0, 1, 2, and 3 generated successfully!")
