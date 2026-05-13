# Quantum Photonic Translator: An Interactive Bargmann UI
**Active R&D Sandbox: Exploring 16-Pin Bus Architectures for CV Photonic Simulation**

**[Lisa Encisco](mailto:intentional.lisa@gmail.com)**  
Updated: 5/10/26

> **PROJECT STATUS:** This repository is a work-in-progress. The core Bargmann Engine is functional, but the architecture is currently transitioning from Sector-Block mapping (v1.0) to an Interleaved Mode-Local model (v2.0) to improve numerical stability.


## Project Scope
This project is an end-to-end web-based interface for **[Xanadu.ai's](https://xanadu.ai/)**  **Mr. Mustard** and **The Walrus**, designed to translate abstract photonic gate sequences into real-time visual feedback. While the application features a high-performance **Svelte 5 / Svelte Flow** frontend, this documentation focuses primarily on the underlying **16-Pin Bargmann Engine**—the custom numerical architecture developed to solve the "State-as-Component" problem in modular quantum circuits.

---

## The Development Journey: From Wrappers to Raw Triples

The evolution of this engine was driven by a fundamental shift from using quantum libraries as a "black box" to treating them as an extensible architectural framework.

### Phase 1: High-Level Wrappers (The Starting Point)
Initially, the project utilized high-level library wrappers (e.g., `State(mixed=True)`) to handle Gaussian operations. While efficient for standard scripts, these abstractions proved restrictive for an interactive, node-based environment. The "Black Box" approach made it difficult to:
* **Isolate Modes:** Standard wrappers often treat the entire system state as a single object, making it nearly impossible to "tap into" or modify a specific mode without affecting the whole.
* **Manage State Persistence:** The UI required a "Reservoir" that stays alive between user interactions. High-level abstractions are typically designed for "one-shot" execution rather than persistent, stateful components.

### Phase 2: The Triple Transition 
To gain direct control over the simulation, the engine was refactored to work directly with **Abc Triples**—the raw algebraic components of the Bargmann representation. This transition required:
* **Manual Contraction:** Implementing the Generalized Bargmann Composition formula (the "Solder" engine) from scratch.
* **The 16-Pin Breakthrough:** Moving from 4-pin (pure state) and 8-pin (basic gate) models to the **16-pin Density Matrix model**. This allowed every mode to have dedicated, bi-directional Ket and Bra pins, finally enabling the "State-as-Component" vision.

### Why the "Hard Way" Helped
By abandoning the convenience of wrappers for the complexity of raw triples, the project achieved:
1.  **Non-Linear Routing:** The ability to connect any gate to any mode-pin in real-time.
2.  **Explicit Noise Injection:** The ability to inject Thermal or Loss states at any point in the circuit by manually bridging the Ket and Bra sectors.
3.  **Stability Awareness:** Direct access to the interaction kernel ($M$-matrix), allowing the engine to diagnose and stabilize numerical caustics that high-level wrappers simply ignore.

## The Architectural Challenge: The 16-Pin Reservoir
In standard quantum libraries, simulation is typically "feed-forward." However, an interactive node-based UI requires a persistent, non-linear state reservoir. To achieve this, the engine transitioned from a standard 4-pin model to a 16-Pin Bus architecture.

### Why 16 Pins?
To treat a 2-mode Density Matrix as a standalone, pluggable component, the engine assigns 8 pins per mode:
* **4 Pins for the Ket (Physical) Sector:** (In-q, In-p, Out-q, Out-p)
* **4 Pins for the Bra (Conjugate) Sector:** (In-q, In-p, Out-q, Out-p)

The doubling allows the simulator to inject Mixed States (Thermal Noise, Information Loss) and manage independent routing for each port without "clobbering" multi-mode data integrity.


#### The "V1.0" Mapping Post-Mortem: Lessons from Mapping 16-Pin Bus

The current version of the engine uses a **Sector-Block Mapping** (grouping all Bra-Inputs, then all Ket-Inputs, etc.). While this simplified the Svelte Flow "cable management" for the UI, it forced the physics engine to jump across non-contiguous memory blocks to perform single-mode operations (e.g., rotating Mode 0 required touching Index 0 and Index 4 simultaneously).   

The initial attempt of **Sector-Blocking** was a design choice driven by the internal logic of multi-mode gates like the **beamsplitter**. Most photonic libraries define the beamsplitter transformation as a unitary acting on a contiguous vector of inputs. To stay compatible with the standard $(A, b, c)$ outputs of these gates, it was intuitive to group all "In" pins together and all "Out" pins together. This allowed for a direct 1-to-1 mapping from the gate's local matrix to a sector of the global reservoir without reshuffling the indices during the contraction process.

The engine uses the **Generalized Bargmann Contraction** $(A, b, c)$ to "solder" components to the reservoir.  
> **Note on Terminology:**
> * **Reservoir:** The global $16 \times 16$ Bargmann $A$-matrix representing the persistent state of the photonic circuit. It acts as a mathematical baseline for the simulation, maintaining the state of all modes simultaneously.
> * **Soldering:** The process of using the **Generalized Bargmann Contraction** to mathematically fuse a discrete gate’s $(A, b, c)$ triples into the global reservoir. This effectively "wires" the component’s logic into the existing circuit state.
   
**Baseline Logic:** $(q_0, p_0, q_1, p_1)_{conj} \dots (q_0, p_0, q_1, p_1)_{phys}$

| Logical Mode | Sector | Input Indices (_q,p_) | Output Indices (_q,p_) |
| :--- | :--- | :--- | :--- |
| **Mode 0** | Ket (Physical): $q_0,p_0$ | [4, 5] | [12, 13] |
| **Mode 0** | Bra (Conjugate): $q_0,p_0$ | [0, 1] | [8, 9] |
| **Mode 1** | Ket (Physical): $q_1,p_1$ | [6, 7] | [14, 15] |
| **Mode 1** | Bra (Conjugate): $q_1,p_1$ | [2, 3] | [10, 11] |

This "Sector-Separation" caused significant overhead in index tracking and was the primary source of "mode-bleed" bugs during the early development of the Svelte-Flask bridge.

#### The "V2.0" Proposed Mapping: Interleaved Mode-Local Indexing
Based on the implementation challenges documented in this PoC, a future refactor would move to **Mode-Local Mapping**. This aligns more closely with the Interleaved approach by keeping the dual-rail variables ($q$ and $p$) for a single mode in adjacent memory.

**Baseline Logic:** $(q, p)_{phys} + (q, p)_{conj}$ per 4-pin block.

| Logical Mode | v2.0 Pin Indices (Ket-In, Bra-In, Ket-Out, Bra-Out) | Physical Coordinate Mapping |
| :--- | :--- | :--- |
| **Mode 0** | [0, 1, 2, 3] | $(q_0, p_0)_{phys} + (q_0, p_0)_{conj}$ |
| **Mode 1** | [4, 5, 6, 7] | $(q_1, p_1)_{phys} + (q_1, p_1)_{conj}$ |
| **Mode 2** | [8, 9, 10, 11] | $(q_2, p_2)_{phys} + (q_2, p_2)_{conj}$ |
| **Mode 3** | [12, 13, 14, 15] | $(q_3, p_3)_{phys} + (q_3, p_3)_{conj}$ |

**Advantages of the Refactored Model:**
1. **Mathematical Locality:** Applying a gate to Mode $N$ only requires a slice of indices $[4N : 4N+4]$, making the `engine.py` logic agnostic to the total number of modes.
2. **Numerical Stability:** Grouping the Ket and Bra sectors locally makes it easier to enforce the $A = A^T$ symmetry required by the Bargmann representation, reducing the chance of non-physical results during deep circuit contractions.
3. **Scalability:** New modes can be appended to the bus without re-indexing the existing reservoir.
---

### Technical Insights & Stability
* **Caustic Identification:** The engine monitors the interaction kernel $M = \mathbb{I} - A_1 A_2$. In high-gain regimes (Squeezing/Thermal), it identifies numerical instabilities where $\det(M) \to 0$, implementing Pseudo-Inverse (PINV) stabilization for the "Gatekeeper" loop.
* **The "Idle Wire" Problem:** In a modular UI, any mode not explicitly targeted by a gate would numerically collapse. This engine implements **Identity Pass-Through Logic** to maintain the persistent identity of idle modes across the 16-pin bus.  

## Future Directions: Towards Interactive State Persistence
A core takeaway from this project is the need for **Mode-Local Abstractions** within photonic simulation libraries. Currently, most backends are optimized for "batch-processing" entire circuits. However, to support real-time, interactive tools, libraries would benefit from a native way to "block" information on specific modes—enabling **Interactive State Persistence**. By allowing a developer to isolate and mutate a single mode's dual-rail variables without re-calculating the global state, the library could significantly reduce numerical overhead for high-mode-count systems. Developing these mode-local persistence layers is a primary goal for future iterations of this engine.

---

## Technical Specifications & Versions
* **Quantum Backend:** Developed and validated against **Mr. Mustard v1.0.0a1** and compatible with **The Walrus**.
* **Numerical Engine:** NumPy / JAX-ready Python 3.x.
* **UI Architecture:** Svelte 5 / Svelte Flow (Source code available upon request).

> **Note:** This repository serves as a technical case study and architectural proof-of-concept. It documents the journey from high-level library wrappers to "bare-metal" algebraic soldering. A local demo and detailed architectural notes are available upon request.





