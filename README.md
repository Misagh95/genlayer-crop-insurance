# Parametric Crop Insurance — An Intelligent Contract on GenLayer

Decentralized parametric crop insurance that evaluates weather data and settles claims using GenLayer's Optimistic Democracy consensus — no central oracle, no human adjuster.

## How It Works

1. A farmer buys a policy via `buy_policy()` and pays a premium (10% of coverage)
2. When a damaging event occurs (drought, heatwave), the farmer calls `claim()`
3. The contract:
   - Fetches rainfall & temperature data from **Open-Meteo API** (free, no key)
   - Validators reach consensus on the fetched data via `run_nondet_unsafe`
   - An LLM compares the weather against policy thresholds
   - Validators agree on the damage **payout_ratio** via `prompt_comparative`
   - Payout is transferred automatically

## Consensus Design

| Step | Mechanism | Details |
|------|-----------|---------|
| Weather fetch | `gl.vm.run_nondet_unsafe` | Leader fetches; validators verify the response has valid structure |
| Damage assessment | `gl.eq_principle.prompt_comparative` | LLM evaluates damage; validators agree on semantically equivalent payout ratio |
| Payout | Deterministic | Parses consensus JSON, calculates coverage * ratio, transfers |

## State

```
PolicyData {
  owner, crop, location, lat, lon,
  coverage, premium, start_ts, end_ts,
  min_rain_mm, max_temp_c,
  claimed, paid
}
```

## Methods

- `buy_policy(crop, location, lat, lon, coverage, start_ts, end_ts, min_rain_mm, max_temp_c)` — payable, creates a policy
- `claim(policy_id)` — triggers weather fetch + LLM assessment, pays out if conditions met
- `get_policy(policy_id)` — view returns policy details
- `my_policies()` — view returns list of caller's policy IDs

## Why This Matters

Parametric insurance is a perfect fit for GenLayer because:
- It **needs** real-world weather data (impossible on deterministic chains)
- It **needs** subjective judgment (is this amount of rain "drought" for wheat?)
- It **needs** decentralized consensus (no single oracle to bribe)
- It's a real financial primitive, not a demo

## Data Source

Uses [Open-Meteo Archive API](https://open-meteo.com/) (free, no API key) for historical weather data.

## Deploy & Test

```bash
# run direct-mode unit tests (no Docker needed)
pip install genlayer-test
pytest tests/ -v
```

1. Open [GenLayer Studio](https://studio.genlayer.com/contracts)
2. Connect your wallet and paste `crop_insurance.py`
3. Deploy (costs zero — testnet GEN from [faucet](https://testnet-faucet.genlayer.foundation/))
4. Call `buy_policy()` with lat/lon of a real farm and a past date range
5. Call `claim()` — validators fetch historical weather data and decide payout

## Files

| File | Purpose |
|------|---------|
| `crop_insurance.py` | The Intelligent Contract |
| `tests/test_direct.py` | Direct-mode unit tests (pytest) |
| `requirements.txt` | Python deps for testing |
| `README.md` | This file |
