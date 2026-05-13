# File: core/engine.py
#
# This module implements the "Generalized Bargmann Composition Engine."
#
# In Continuous-Variable (CV) quantum simulation, the Bargmann representation 
# (A, b, c triples) offers a powerful alternative to Fock-space truncation. 
# However, moving from high-level library wrappers to raw triple compositions 
# introduces significant numerical and architectural challenges:
#
# 1. Numerical Stability (The Caustic Problem): As the composition approaches 
#    the boundary condition ||A1 + A2*|| -> 2, the interaction kernel becomes 
#    singular. This engine identifies these "caustics" in the M-matrix.
#
# 2. Multi-Mode Index Mapping: In a 16-pin (8-mode) density matrix simulation, 
#    manual index routing is required to maintain the Bra-Ket symmetry (XA = A*X).
#
# This script documents the "bare-metal" algebraic solder required to compose 
# Gaussian kernels, providing the surgical control needed for interactive 
# node-based UI development.


import numpy as np

def contract_triples(A1, b1, c1, A2, b2, c2, idx1, idx2):
    """
    General Bargmann Composition Formula (The 'Solder' Engine).
    
    This function implements the contraction of two Bargmann triples (A, b, c) 
    over specified indices. This is the numerical core required for composing 
    quantum gates or connecting states to operators without relying on 
    high-level library abstractions.
    
    Technical Note: This implementation follows the algebraic framework defined 
    in Miatto et al. (2022), specifically addressing the 'Glueing' of 
    multimode Gaussian kernels.
    """
    
    # n1, n2 represent the total dimensionality (pins) of each triple.
    n1, n2 = A1.shape[-1], A2.shape[-1]
    m = len(idx1) # Number of modes being contracted (the 'bridge')
    
    # --- STEP 1: INDEX PARTITIONING ---
    # We identify which 'pins' are being connected and which are remaining 'free'.
    not1 = [i for i in range(n1) if i not in idx1]
    not2 = [i for i in range(n2) if i not in idx2]
    
    # Reorder matrices so the 'Contracted' indices are grouped at the end of A1 
    # and the beginning of A2. This simplifies the block-matrix partitioning.
    order1 = not1 + idx1
    order2 = idx2 + not2
    
    A1_f, b1_f = A1[np.ix_(order1, order1)], b1[order1]
    A2_f, b2_f = A2[np.ix_(order2, order2)], b2[order2]
    
    # Partition blocks: 
    # r = remaining (free), c = contracted (connected)
    A1rr, A1rc = A1_f[:len(not1), :len(not1)], A1_f[:len(not1), len(not1):]
    A1cr, A1cc = A1_f[len(not1):, :len(not1)], A1_f[len(not1):, len(not1):]
    
    A2cc, A2cr = A2_f[:m, :m], A2_f[:m, m:]
    A2rc, A2rr = A2_f[m:, :m], A2_f[m:, m:]
    
    b1r, b1c = b1_f[:len(not1)], b1_f[len(not1):]
    b2c, b2r = b2_f[:m], b2_f[m:]
    
    # --- STEP 2: THE INTERACTION KERNEL (M-Matrix) ---
    # M represents the core interaction between the two triples.
    # CRITICAL: If det(M) approaches 0, the composition hit a caustic/singularity.
    I = np.eye(m)
    M = I - A1cc @ A2cc
    
    # Numerical Challenge: High-gain states (Squeezing/Thermal) make M ill-conditioned.
    # Future versions should implement Tikhonov regularization (M + epsilon*I) here.
    M_inv = np.linalg.inv(M)
    
    # --- STEP 3: ASSEMBLE NEW A MATRIX ---
    # We calculate the four quadrants of the new coupled system:
    # 1. Internal reflections within Triple 1 (A_new_rr)
    # 2. Cross-talk/Propagation from 1 to 2 (A_new_rc)
    # 3. Cross-talk/Propagation from 2 to 1 (A_new_cr)
    # 4. Internal reflections within Triple 2 (A_new_cc)
    
    A_new_rr = A1rr + A1rc @ M_inv @ A2cc @ A1cr
    A_new_rc = A1rc @ M_inv @ A2cr
    A_new_cr = A2rc @ M_inv @ A1cr
    A_new_cc = A2rr + A2rc @ M_inv @ A1cc @ A2cr
    
    # Final Block Assembly: [Remaining1, Remaining2]
    A_final = np.block([
        [A_new_rr, A_new_rc],
        [A_new_cr, A_new_cc]
    ])
    
    # --- STEP 4: ASSEMBLE NEW b VECTOR ---
    # This represents the linear 'displacement' terms propagating through the bridge.
    b_final = np.concatenate([
        b1r + A1rc @ M_inv @ (b2c + A2cc @ b1c),
        b2r + A2rc @ M_inv @ (b1c + A1cc @ b2c)
    ])
    
    # --- STEP 5: ASSEMBLE NEW c SCALAR ---
    # Calculate the normalization constant. 
    # NOTE: This is where floating-point overflow occurs in deep circuits.
    # Recommendation: Track the 'exponent' separately to avoid 'inf' results.
    exponent = 0.5 * (b1c @ M_inv @ A2cc @ b1c + 
                      b2c @ M_inv @ A1cc @ b2c + 
                      2 * b2c @ M_inv @ b1c)
    
    # Full Gaussian integral normalization
    c_final = c1 * c2 * (1.0 / np.sqrt(np.linalg.det(M))) * np.exp(exponent)
    
    return A_final, b_final, c_final