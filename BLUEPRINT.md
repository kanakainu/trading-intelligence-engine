# 🧠 Trading Intelligence Engine (TIE)
# Architecture Blueprint
## Version 1.0
Status: 🔒 FROZEN

---

# 1. Vision
Trading Intelligence Engine (TIE) adalah Knowledge-Driven Trading Reasoning Engine yang bersifat modular, extensible, dan strategy-agnostic.
TIE tidak mengenal metodologi trading tertentu.
Semua metodologi (Bystra, ICT, SMC, CRT, dll.) dipasang sebagai Knowledge Pack.

---

# 2. Core Philosophy
Market -> Facts -> Knowledge -> Setup -> Decision -> Execution
Engine tidak pernah langsung mengubah Market menjadi BUY/SELL.

---

# 3. Architecture
Trading Runtime -> TIE (Compiler -> Graph -> Context -> Detector -> Facts -> Setup -> Decision -> Explanation) -> Execution Adapter -> Broker

---

# 4. Core Modules
## Runtime
Responsibility: Scheduler, Market Data Collection, Call TIE, Receive Decision, Forward to Broker. Tidak boleh memiliki trading logic.

## Knowledge Compiler
Input: Knowledge Pack (YAML). Output: Knowledge Objects.

## Knowledge Graph
Menyimpan seluruh object knowledge dan relationship.

## Context Engine
Menghasilkan market context (Trend, ATR, Spread, Session, Volatility, News). Tidak mendeteksi pattern.

## Detector Engine
Menghasilkan FACT. Tidak boleh menghasilkan BUY, SELL, Entry, SL, TP.

## Facts Engine
Menggabungkan seluruh detector menjadi satu kumpulan fakta.

## Setup Engine
Menggunakan Facts + Knowledge Graph. Output: PASS/FAIL. Tidak boleh BUY.

## Decision Engine
Menggunakan Setup. Output: BUY, SELL, WAIT.

## Explanation Engine
Menjelaskan alasan keputusan.

## Execution Adapter
Mengirim order. Tidak memiliki trading logic.

---

# 5. Repository Structure
docs/, knowledge/, core/, adapters/, plugins/, datasets/, tests/, examples/, scripts/

---

# 6. Knowledge Pack Structure
knowledge/{bystra, ict, smc, crt, custom}

---

# 7. Core Structure
core/{compiler, graph, context, detectors, facts, setup, decision, explanation, execution}

---

# 8. Processing Flow
Market Data -> Context -> Knowledge Graph -> Detector -> Facts -> Setup -> Decision -> Explanation -> Execution -> Broker

---

# 9. Golden Rules
Rule 1: Engine tidak mengenal strategy.
Rule 2: Strategy adalah Knowledge Pack.
Rule 3: Detector hanya menghasilkan Facts.
Rule 4: Facts Engine hanya menggabungkan fakta.
Rule 5: Setup Engine hanya menghasilkan PASS atau FAIL.
Rule 6: Decision Engine adalah satu-satunya layer yang boleh menghasilkan BUY, SELL, atau WAIT.
Rule 7: Execution Adapter hanya mengirim order.
Rule 8: Semua trading rule berasal dari Knowledge Pack.
Rule 9: Tidak boleh ada hardcode trading rule di Core Engine.
Rule 10: Core Engine tidak boleh bergantung pada metodologi tertentu.

---

# 10. Repository Philosophy
Core Engine + Knowledge Pack = Trading Intelligence Engine.

---

# 11. Migration Strategy
Current Riri Runtime -> Parallel building TIE -> Migrate Bystra setup -> Parallel testing -> Switch Runtime -> Delete old bystra_bot/.

---

# 12. Architecture Status
Architecture: LOCKED. Version: 1.0. Status: FROZEN.
