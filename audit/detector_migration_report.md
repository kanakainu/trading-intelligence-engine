# Detector Migration Report — Sprint 5.3

## Executive Summary
Seluruh detector legacy dari `detector.py` telah dimigrasikan ke dalam module independen di bawah folder `detectors/`. Setiap detector sekarang mengikuti `DetectorInterface` TIE dan hanya menghasilkan `Fact` tanpa membuat keputusan trading.

## 1. Migrated Detectors
Berikut adalah pemetaan detector yang telah dimigrasikan:

| Legacy Method | New Module | Status | Output Fact |
| :--- | :--- | :--- | :--- |
| `_detect_hybrid_snrc` | `hybrid1_detector.py` | **DONE** | `HYBRID_1` |
| `_detect_hybrid_snrc` | `hybrid2_detector.py` | **DONE** | `HYBRID_2` |
| `_detect_hybrid_snrc` | `snrc1_detector.py` | **DONE** | `SNRC_1` |
| `_detect_hybrid_snrc` | `snrc2_detector.py` | **DONE** | `SNRC_2` |
| `_detect_hybrid_snrc` | `snrc3_detector.py` | **DONE** | `SNRC_3` |
| `_detect_quasimodo` | `qmr_detector.py` | **DONE** | `QMR` |
| `_detect_quasimodo` | `qmc_detector.py` | **DONE** | `QMC` |
| `_detect_quasimodo` | `qm2p_detector.py` | **DONE** | `QM2P` |
| `_detect_quasimodo` | `qmm_detector.py` | **DONE** | `QMM` |
| `_detect_blindspot` | `blindspot_detector.py` | **DONE** | `BLINDSPOT_1` |
| `_detect_blindspot` | `blindspot2_detector.py` | **DONE** | `BLINDSPOT_2` |
| `_detect_manipulation`| `manipulation_detector.py` | **DONE** | `MANIPULATION` |
| `_detect_clab` | `clab_detector.py` | **DONE** | `CLAB` |

## 2. Key Changes
- **No BUY/SELL:** Detector tidak lagi menentukan arah trading secara eksplisit sebagai status, melainkan sebagai metadata dalam `Fact`.
- **Interface Driven:** Menggunakan `DetectorInterface` dari TIE Core.
- **Fact Driven:** Output berupa `List[Fact]` yang akan dikonsumsi oleh `FactsEngine` dan `SetupEngine`.

## 3. Regression & Verification
- Unit tests telah disiapkan untuk memverifikasi pendeteksian pola dasar.
- Logic deteksi identik dengan legacy untuk memastikan konsistensi hasil.

## 4. Next Step
Lanjutkan ke **Sprint 5.4 Skill Migration** untuk memigrasikan fungsi utilitas (ATR, Lot Calc, News) menjadi reusable skills.
