# File: core/gates.py
#
# This module defines the library of Photonic Quantum Gates and States in the 
# Bargmann (A, b, c) representation, optimized for a 16-pin "State-as-Component" model.
#
# Technical Highlights:
# 1. Evolution to 16-Pins: The architecture transitioned from 4 to 8, and finally 16 pins
#    to solve the "Component-Isolation" problem. While an 8-pin model suffices for 
#    pure-state gate transformations, 16 pins are required to treat a 2-mode Density 
#    Matrix as a standalone plug-able component with independent Bra and Ket 
#    routing for each port.
#
# 2. "Wire" Logic: Implements manual pass-through terms for idle modes. Without 
#    these identity bridges (A[i, o] = 1.0), unselected modes in a multi-mode 
#    circuit would numerically collapse to vacuum during composition.
#
# 3. Dual-Rail (Bra-Ket) Promotion: Functions like `promote_to_dm` handle the 
#    symmetry requirements of Density Matrices. This ensures that the 'Ket' (physical) 
#    and 'Bra' (conjugate) sectors are correctly mirrored across the 16x16 
#    state space.

import numpy as np

def vacuum_state_Abc(n):
    """
    Returns the vacuum state triples for an n-mode system.
    
    Why 16 pins? (for n=2): 
    The jump to 16 pins was necessitated by the shift from 'State-as-Vector' to 
    'State-as-Density-Matrix'. By providing 4 pins per mode (Ket-In, Ket-Out, 
    Bra-In, Bra-Out), we allow the UI to treat the state as a modular component 
    capable of receiving feedback, thermal noise, and loss injections that 
    require simultaneous access to the physical and conjugate sectors.
    """
    A = np.zeros((4 * n, 4 * n), dtype=complex)
    b = np.zeros(4 * n, dtype=complex)
    c = 1.0 + 0j
    return A, b, c


def squeezing_gate_Abc(r, phi, target_mode=0):
    """
    Squeezing Operator in the Bargmann representation.
    Calculates hyperbolic transformations (tanh/sech) for the A-matrix.
    """
    A = np.zeros((8, 8), dtype=complex)
    th, sh = np.tanh(r), 1.0 / np.cosh(r)
    exp_p = np.exp(1j * phi)
    exp_p_half = np.exp(1j * phi / 2.0)

    # Pin mapping: Mode 0: [0,1]->[4,5] | Mode 1: [2,3]->[6,7]
    if target_mode == 0:
        in_p, out_p = [0, 1], [4, 5]
        idle_in, idle_out = [2, 3], [6, 7]
    else:
        in_p, out_p = [2, 3], [6, 7]
        idle_in, idle_out = [0, 1], [4, 5]

    # --- THE "WIRE" LOGIC ---
    # Preserves the identity of the unselected (idle) mode during contraction.
    for i, o in zip(idle_in, idle_out):
        A[i, o] = 1.0; A[o, i] = 1.0

    # --- THE SQUEEZE LOGIC ---
    for i, o in zip(in_p, out_p):
        A[i, o] = sh * exp_p_half
        A[o, i] = sh * exp_p_half

    A[out_p[0], out_p[1]] = th * exp_p
    A[out_p[1], out_p[0]] = th * exp_p
    A[in_p[0], in_p[1]] = -th * np.conj(exp_p)
    A[in_p[1], in_p[0]] = A[in_p[0], in_p[1]]

    return A, np.zeros(8, dtype=complex), 1.0

def beamsplitter_gate_Abc(theta: float, phi: float = 0.0):
    """
    Two-mode Beamsplitter.
    Implements transmission (Stay) and reflection (Swap) terms.
    """
    c, s = np.cos(theta), np.sin(theta)
    A = np.zeros((8, 8), dtype=complex)

    # Transmission (Transmission of Mode 0 and Mode 1)
    A[0, 4] = c; A[4, 0] = c
    A[1, 5] = c; A[5, 1] = c
    A[2, 6] = c; A[6, 2] = c
    A[3, 7] = c; A[7, 3] = c

    # Reflection (Interaction between Mode 0 and Mode 1)
    A[0, 6] = s; A[6, 0] = s
    A[1, 7] = s; A[7, 1] = s
    A[2, 4] = -s; A[4, 2] = -s
    A[3, 5] = -s; A[5, 3] = -s

    return A, np.zeros(8, dtype=complex), 1.0 + 0j

def promote_to_dm(A_8, b_8, c_8, target_mode=None):
    """
    Converts a Pure State triple (8x8) into a Density Matrix triple (16x16).
    This manually mirrors the Ket sector into the Bra sector to allow for 
    mixed-state operations (Thermal, Loss, etc.).
    """
    A_16 = np.zeros((16, 16), dtype=complex)
    
    # BRA (Conjugate) Sector mapping
    A_16[0:4, 0:4] = np.conj(A_8[0:4, 0:4]) 
    A_16[8:12, 8:12] = np.conj(A_8[4:8, 4:8])
    A_16[0:4, 8:12] = np.conj(A_8[0:4, 4:8])
    A_16[8:12, 0:4] = np.conj(A_8[4:8, 0:4])

    # KET (Physical) Sector mapping
    A_16[4:8, 4:8] = A_8[0:4, 0:4]
    A_16[12:16, 12:16] = A_8[4:8, 4:8]
    A_16[4:8, 12:16] = A_8[0:4, 4:8]
    A_16[12:16, 4:8] = A_8[4:8, 0:4]

    b_16 = np.concatenate([b_8, b_8.conj()]) 
    # Bra Sector Pins: 0-3, 8-11 | Ket Sector Pins: 4-7, 12-15
    b_16[0:4] = np.conj(b_8[0:4])
    b_16[8:12] = np.conj(b_8[4:8])
    b_16[4:8] = b_8[0:4]
    b_16[12:16] = b_8[4:8]
       
    return A_16, b_16, float(np.abs(c_8)**2)

def thermal_state(nbar, mode=0):
    """
    Generates a Thermal (Mixed) state. 
    Explicitly populates the entropy bridge (correlations between Ket and Bra).
    """
    A_16 = np.zeros((16, 16), dtype=complex)
    b_16 = np.zeros(16, dtype=complex)
    n = float(nbar)
    mu = n / (n + 1.0) if n > 0 else 0.0
    off = 0 if mode == 0 else 2

    # Population terms (Physical + Mirror)
    A_16[8+off, 8+off] = mu; A_16[9+off, 9+off] = mu
    A_16[12+off, 12+off] = mu; A_16[13+off, 13+off] = mu

    # Entropy Bridge (Correlations between Bra and Ket sectors)
    A_16[8+off, 12+off] = mu; A_16[12+off, 8+off] = mu
    A_16[9+off, 13+off] = mu; A_16[13+off, 9+off] = mu

    c_16 = 1.0 / (n + 1.0)
    return A_16, b_16, c_16

def rotation_gate_Abc(phi: float, target_mode: int):
    """Phase Rotation Gate."""
    A = np.zeros((8, 8), dtype=complex)
    phase = np.exp(1j * phi)
    in_p, out_p = (0, 4) if target_mode == 0 else (2, 6)

    # Active Rotation
    A[out_p, in_p] = phase; A[in_p, out_p] = phase 
    A[out_p + 1, in_p + 1] = np.conj(phase); A[in_p + 1, out_p + 1] = np.conj(phase)

    # Idle Wire (Identity for the non-target mode)
    idle_in, idle_out = (2, 6) if target_mode == 0 else (0, 4)
    A[idle_out, idle_in] = 1.0; A[idle_in, idle_out] = 1.0
    A[idle_out + 1, idle_in + 1] = 1.0; A[idle_in + 1, idle_out + 1] = 1.0
    
    return A, np.zeros(8, dtype=complex), 1.0

def displacement_gate_Abc(x, y, target_mode=0):
    """Coherent Displacement Gate (D). Sets the b-vector for linear translations."""
    alpha = complex(x, y) * 2.0
    A = np.zeros((8, 8), dtype=complex); b = np.zeros(8, dtype=complex)

    # Idle Wire
    if target_mode == 0:
        A[6, 2] = 1.0; A[7, 3] = 1.0
    else:
        A[4, 0] = 1.0; A[5, 1] = 1.0

    # Active Displacement (Linear shift in the b-vector)
    out_p, in_p = (4, 0) if target_mode == 0 else (6, 2)
    b[out_p] = alpha; b[out_p + 1] = np.conj(alpha)
    b[in_p] = -np.conj(alpha); b[in_p + 1] = -alpha

    c = np.exp(-0.5 * np.abs(alpha)**2)
    return A, b, c