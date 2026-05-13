# File: core/simulate.py
# ==============================================================================
# ARCHITECTURAL OVERVIEW: THE 16-PIN RESERVOIR PATTERN (PoC)
# ==============================================================================
# In standard quantum libraries, simulation is "feed-forward": a state is passed 
# through a fixed sequence of gates. However, in a node-based UI, components 
# can be connected non-linearly and interactively.
#
# To solve this, this simulator implements a "Global Reservoir" model:
#
# 1. 16-Pin Bus: Each of the 2 modes is assigned 8 pins (4 for the Ket sector, 
#    4 for the Bra sector). This allows the simulator to handle Mixed States 
#    (Thermal/Loss) as modular components.
#
# 2. State Persistence: Unlike batch-oriented libraries, this PoC maintains a 
#    persistent 16-pin reservoir (res_A, res_b). This allows a user to 
#    interactively drag nodes and inject noise or gates without re-initializing 
#    the entire state vector.
#
# 3. Path-Tracing & Sequential Solder: The system reverse-traces the UI graph 
#    to find the "Chain of Ancestry." It then "solders" each component to the 
#    reservoir one-by-one using the Generalized Bargmann Contraction (A, b, c).
#
# 4. Mode Isolation (Silo Updates): By using targeted index updates, we ensure 
#    that a gate acting on Mode 0 cannot numerically "clobber" the data stored 
#    in Mode 1's pins, maintaining multi-mode integrity.
#
# 5. Architectural Direction: As a Proof-of-Concept, this file utilizes a 
#    monolithic procedural loop. Future iterations will adopt an Object-Oriented 
#    or Actor-Model approach, moving math-heavy logic into individual 
#    'Component Class' modules. This will facilitate parallelized processing 
#    and a cleaner separation between the API layer and the Bargmann Engine.
# ==============================================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import traceback

from engine import contract_triples 
from gates import (vacuum_state_Abc, squeezing_gate_Abc, beamsplitter_gate_Abc, 
                   rotation_gate_Abc, promote_to_dm, thermal_state, displacement_gate_Abc)

app = Flask(__name__)
CORS(app)

def get_ordered_path(nodes, edges, plot_id):
    """
    Reverse-trace the graph to identify the "Chain of Ancestry."
    Only nodes that eventually reach an output (Wigner/Detector) are computed.
    """
    path = []
    current_id = plot_id
    while current_id:
        node = next((n for n in nodes if n['id'] == current_id), None)
        if not node: break
        path.append(node)
        incoming_edge = next((e for e in edges if e['target'] == current_id), None)
        current_id = incoming_edge['source'] if incoming_edge else None
    return path[::-1]

@app.route('/simulate', methods=['POST'])
def simulate():
    try:
        data = request.json
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        
        # --- 1. THE UI SINK DISCOVERY ---
        # Locate the output components (plots) to begin the dependency trace.
        m0_plot = next((n for n in nodes if n.get('type') == 'wigner' and n.get('mode') == 0), None)
        m1_plot = next((n for n in nodes if n.get('type') == 'wigner' and n.get('mode') == 1), None)

        path0 = get_ordered_path(nodes, edges, m0_plot['id']) if m0_plot else []
        path1 = get_ordered_path(nodes, edges, m1_plot['id']) if m1_plot else []

        # --- 2. RESERVOIR INITIALIZATION ---
        # We start with the "Universal Bridge": a 16x16 identity matrix that 
        # allows signals to pass through "empty" mode-wires without loss.
        res_A = np.zeros((16, 16), dtype=complex)
        for i in range(8):
            res_A[i, i+8] = 1.0; res_A[i+8, i] = 1.0
            
        res_b = np.zeros(16, dtype=complex)
        res_c = 1.0

        # --- 3. GRAPH PRUNING ---
        # Identify active nodes to avoid redundant physics calculations.
        state_types = ['vacuum', 'thermal', 'squeeze']
        has_v0 = any(n['type'] in state_types for n in path0)
        has_v1 = any(n['type'] in state_types for n in path1)

        if has_v0 or has_v1:
            wigner_ids = {n['id'] for n in path0} | {n['id'] for n in path1}
            
            detector_ids = set()
            for n in nodes:
                if n.get('type') == 'measurement':
                    d_path = get_ordered_path(nodes, edges, n['id'])
                    if any(p['type'] in ['vacuum', 'thermal', 'squeeze', 'rotation', 'displacement'] for p in d_path):
                        detector_ids.update(p['id'] for p in d_path)
            
            bs_ids = {n['id'] for n in nodes if n.get('type') == 'beamsplitter'}
            sq_ids = {n['id'] for n in nodes if n.get('type') == 'squeeze'}
            vac_ids = {n['id'] for n in nodes if n.get('type') == 'vacuum'}
            det_ids = {n['id'] for n in nodes if n.get('type') == 'measurement'}
            therm_ids = {n['id'] for n in nodes if n.get('type') == 'thermal'}
            displ_ids = {n['id'] for n in nodes if n.get('type') == 'displacement'}
            rot_ids = {n['id'] for n in nodes if n.get('type') == 'rotation' or n.get('data', {}).get('gateType') == 'rotation'}

            active_ids = wigner_ids | detector_ids | bs_ids | sq_ids | vac_ids | det_ids | therm_ids | displ_ids | rot_ids

            # --- 4. EXECUTION LOOP (The Physics Heart) ---
            # Sort by causality: Sources -> Gates -> Measurements.
            ordered_nodes = sorted(nodes, key=lambda n: 0 if n.get('type') in ['vacuum', 'thermal'] else (1 if n.get('type') != 'measurement' else 2))

            for node in ordered_nodes:
                if node['id'] not in active_ids: continue

                A_n, b_n, c_n = None, None, 1.0 
                node_type = node.get('type')

                # CASE: THERMAL NOISE (State Injection)
                if node_type == 'thermal':
                    val = node.get('r', 0.0)
                    nbar = float(val)
                    m = int(node.get('mode', 0))
                    A_n, b_n, c_n = thermal_state(nbar, mode=m)
                    
                    # Clear the "Empty Wire" bridge to make room for the state
                    off = 0 if m == 0 else 2
                    res_A[off, 8+off] = 0.0; res_A[8+off, off] = 0.0
                    res_A[1+off, 9+off] = 0.0; res_A[9+off, 1+off] = 0.0
                    res_A[4+off, 12+off] = 0.0; res_A[12+off, 4+off] = 0.0
                    res_A[5+off, 13+off] = 0.0; res_A[13+off, 5+off] = 0.0

                    res_A += A_n
                    res_c *= c_n
                    A_n = None # Skip Gatekeeper math

                # CASE: DISPLACEMENT (Mean-Vector Translation)
                elif node_type == 'displacement':
                    x, y, m = float(node.get('x', 0.0)), float(node.get('y', 0.0)), int(node.get('mode', 0))
                    A_8, b_8, c_8 = displacement_gate_Abc(x, y, target_mode=m)
                    A_n, b_n, c_n = promote_to_dm(A_8, b_8, c_8)
                    res_b += b_n; res_c *= c_n
                    continue 

                # CASE: SQUEEZING GATE
                elif node_type == 'squeeze':
                    r = float(node.get('r', 0.0))
                    phi = float(node.get('phi', 0.0)) * 2 
                    m = int(node.get('mode', 0))
                    A_8, b_8, c_8 = squeezing_gate_Abc(r, phi, target_mode=m)
                    A_n, b_n, c_n = promote_to_dm(A_8, b_8, c_8)

                # CASE: PHASE ROTATION
                elif node_type == 'rotation':
                    phi = float(node.get('phi', 0.0))
                    m = int(node.get('mode', 0))
                    A_8, b_8, c_8 = rotation_gate_Abc(phi, m)
                    A_n, b_n, c_n = promote_to_dm(A_8, b_8, c_8)

                # CASE: BEAMSPLITTER
                elif node_type == 'beamsplitter':
                    theta = float(node.get('value', node.get('r', 0.0)))
                    A_8, b_8, c_8 = beamsplitter_gate_Abc(theta)
                    A_n, b_n, c_n = promote_to_dm(A_8, b_8, c_8)

                elif node_type == 'measurement':
                    continue 

                # --- 5. THE GATEKEEPER (Bargmann Contraction Engine) ---
                if A_n is not None or b_n is not None:
                    in_idx, out_idx = list(range(8)), list(range(8, 16))

                    # DATA HANDOFF: Move the Reservoir's "Output" to "Input" for the next gate
                    if np.any(res_A[np.ix_(out_idx, out_idx)]) or np.any(res_b[out_idx]):
                        res_A[np.ix_(in_idx, in_idx)] = res_A[np.ix_(out_idx, out_idx)]
                        res_b[in_idx] = res_b[out_idx]
                        res_A[np.ix_(out_idx, out_idx)] = 0.0
                        res_b[out_idx] = 0.0

                    # THE SNAPSHOT: Deep copy prevents mode-bleed during simultaneous updates
                    if 'res_A_snapshot' not in locals() and node_type not in ['vacuum', 'thermal']:
                        res_A_snapshot = res_A.copy()

                    A11, A12, A21, A22 = A_n[np.ix_(in_idx, in_idx)], A_n[np.ix_(in_idx, out_idx)], A_n[np.ix_(out_idx, in_idx)], A_n[np.ix_(out_idx, out_idx)]
                    b1, b2 = b_n[in_idx], b_n[out_idx]
                    
                    if 'res_A_snapshot' in locals():
                        current_state = res_A_snapshot[np.ix_(in_idx, in_idx)]
                    else:
                        current_state = res_A[np.ix_(in_idx, in_idx)]
                    current_b = res_b[in_idx]

                    # NUMERICAL STABILITY: Using Pseudo-Inverse (PINV) to handle near-caustics
                    M_inv = np.linalg.pinv(np.eye(8) - current_state @ A11)
                    formal_transform = A21 @ M_inv @ current_state @ A12

                    # THE SILO UPDATE: Crucial for multi-mode integrity. 
                    m = int(node.get('mode', 0))
                    target_pins = [8, 9, 12, 13] if m == 0 else [10, 11, 14, 15]
                    source_idx = [0, 1, 4, 5] if m == 0 else [2, 3, 6, 7]

                    res_A[np.ix_(target_pins, target_pins)] = (
                        A22[np.ix_(source_idx, source_idx)] + 
                        formal_transform[np.ix_(source_idx, source_idx)]
                    )
                    res_b[target_pins] = (
                        b2[source_idx] + 
                        (A21 @ M_inv @ (current_b + current_state @ b1))[source_idx]
                    )
                    res_c *= c_n * np.sqrt(np.abs(np.linalg.det(M_inv)))

        # --- 6. UI MAPPING (Wigner Projection) ---
        ui_A = np.zeros((4, 4), dtype=complex)
        k = res_A[12:16, 12:16] 
        
        ui_A[0, 0] = k[0, 0] + res_A[8, 12]   # Mode 0 q-width + entropy
        ui_A[2, 2] = k[1, 1] + res_A[9, 13]   # Mode 0 p-width + entropy
        ui_A[1, 1] = k[2, 2] + res_A[10, 14]  # Mode 1 q-width + entropy
        ui_A[3, 3] = k[3, 3] + res_A[11, 15]  # Mode 1 p-width + entropy
        ui_A[0, 2], ui_A[2, 0] = k[0, 1], k[1, 0]
        ui_A[1, 3], ui_A[3, 1] = k[2, 3], k[3, 2]

        final_c = 1.0 if (has_v0 or has_v1) else 0.0

        # --- 7. DETECTOR EXTRACTION (The Homodyne Probe) ---
        detector_results = {}
        for node in nodes:
            if node.get('type') == 'measurement' and node['id'] in active_ids:
                phi_ui = float(node.get('phi', 0.0))
                m = int(node.get('mode', 0))
                q_idx = 12 if m == 0 else 14
                p_idx = 13 if m == 0 else 15

                phi_lo = phi_ui + (3 * np.pi / 4) 
                cos_p, sin_p = np.cos(phi_lo), np.sin(phi_lo)

                A_qq = res_A[q_idx, q_idx].real
                A_pp = res_A[p_idx, p_idx].real
                A_qp = res_A[q_idx, p_idx].real

                A_phi = (A_qq * cos_p**2 + A_pp * sin_p**2 + 2 * A_qp * cos_p * sin_p)
                ui_sigma = np.sqrt(np.abs((1 + A_phi) / (1 - A_phi)))

                alpha_complex = res_b[q_idx]
                alignment_phase = np.exp(-1j * (5 * np.pi / 4))
                alpha_aligned = alpha_complex * alignment_phase
                Q, P = alpha_aligned.real, alpha_aligned.imag
                ui_mean = (Q * cos_p + P * sin_p) / 2.0
                quad_power = (ui_mean**2) + (ui_sigma**2)

                detector_results[node['id']] = {
                    "mean": round(float(ui_mean), 4),
                    "sigma": round(float(ui_sigma), 4),
                    "measuredValue": round(float(quad_power), 4)
                }

        return jsonify({
            "A": {"real": ui_A.real.tolist(), "imag": ui_A.imag.tolist()},
            "b": {"real": res_b[12:16].real.tolist(), "imag": res_b[12:16].imag.tolist()},
            "c": {"real": float(final_c), "imag": 0.0},
            "measurement": detector_results
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    app.run(port=5000, debug=True)