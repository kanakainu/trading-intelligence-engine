# Brain Migration Report — Sprint 5.2

## Executive Summary
Laporan ini merinci pemetaan tanggung jawab (responsibility mapping) dari legacy "Brain" di Riri SDK ke dalam arsitektur Trading Intelligence Engine (TIE) Phase 3 & 4. Sesuai arsitektur TIE, konsep "Brain" dihilangkan (DEPRECATED) dan fungsinya didistribusikan ke module TIE yang lebih granular dan terstandardisasi.

---

## 1. MarketBrain
**Responsibility:** Mengumpulkan data pasar mentah dan mengubahnya menjadi konteks yang bermakna (Trend, Volatility, Session, ATR).

| Function/Logic | TIE Target Module | Status | Notes |
| :--- | :--- | :--- | :--- |
| Candle fetching | `Market Data Adapter` | **DELETE** | Sudah ditangani adapter framework. |
| Trend analysis | `Context Engine` | **MOVE** | Menggunakan `Trend` enum di TIE core. |
| Session detection | `Context Engine` | **MOVE** | Menggunakan `Session` enum di TIE core. |
| ATR calculation | `Context Engine` | **MOVE** | Pindah ke analytical skills di context layer. |
| Volatility State | `Context Engine` | **MOVE** | Menggunakan `Volatility` enum di TIE core. |
| Data Normalization | `Fact Compiler` | **MOVE** | Konversi market data ke `TypedFact`. |

---

## 2. DecisionBrain
**Responsibility:** Memilih setup terbaik dari sinyal yang tersedia dan menentukan aksi (BUY/SELL/WAIT) berdasarkan reasoning (LLM/Rule).

| Function/Logic | TIE Target Module | Status | Notes |
| :--- | :--- | :--- | :--- |
| Signal selection | `Decision Pipeline` | **MOVE** | Ranking kandidat dilakukan di pipeline. |
| Reasoning (LLM/Rule) | `Reasoning Engine` | **MOVE** | TIE menggunakan `ReasoningResult` & `Candidate`. |
| Confidence scoring | `Setup Resolver` | **MOVE** | Scoring berdasarkan pemenuhan dependensi fakta. |
| Explanation generation| `Explanation Engine` | **MOVE** | TIE memiliki dedicated explanation generator. |
| Workspace writing | `Intelligence Runtime` | **DELETE** | Digantikan oleh `ExecutionContext` management. |

---

## 3. RiskBrain
**Responsibility:** Melakukan validasi terakhir terhadap parameter trading (Spread, SL/TP, RR) sebelum eksekusi.

| Function/Logic | TIE Target Module | Status | Notes |
| :--- | :--- | :--- | :--- |
| Spread validation | `Rule Engine` | **MOVE** | Validasi sebagai `AtomicRule` (spread < threshold). |
| RR validation | `Rule Engine` | **MOVE** | Validasi sebagai `AtomicRule`. |
| SL/TP distance check | `Rule Engine` | **MOVE** | Menjadi bagian dari `SetupMatch` validation. |
| Rejection logic | `Decision Pipeline` | **MOVE** | Decision layer yang memutus status `REJECTED`. |
| Symbol Config mgmt | `Config Module` | **MOVE** | Pindah ke `RiskConfig` di Phase 4.6. |

---

## 4. PositionBrain
**Responsibility:** Mengelola posisi yang sedang berjalan (Trailing SL, Break-Even, Early Exit).

| Function/Logic | TIE Target Module | Status | Notes |
| :--- | :--- | :--- | :--- |
| Trailing Stop | `Position Manager` | **KEEP** | Tetap di Runtime (Phase 4.7). |
| Break-Even trigger | `Position Manager` | **KEEP** | Tetap di Runtime. |
| Reversal exit | `Position Manager` | **KEEP** | Logic deteksi reversal bisa panggil TIE. |
| Circuit breaker | `Position Manager` | **KEEP** | Financial safety tetap concern manager. |

---

## Conclusion
Seluruh tanggung jawab cerdas (intelligence) dari legacy Brain telah memiliki pemetaan ke module TIE Phase 3 (Compiler) dan Phase 4 (Runtime SDK). Implementasi migrasi akan menghilangkan `riri_sdk/brains/` sepenuhnya dan menggantinya dengan pemanggilan orchestrator TIE.

**Sasa's Recommendation:** Lanjutkan ke **5.3 Detector Migration** untuk mulai memindahkan deteksi pola teknis mentah ke TIE Detector Interface.
