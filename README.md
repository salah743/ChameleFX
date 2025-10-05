# ChameleFX — Phase 0 (Core Risk Engine)

Automated risk management engine that enforces institutional-level discipline via hard-coded architecture.

## Quick Start
1. Create a copy of `.env.example` as `.env` and fill MT5 credentials.
2. Run Setup Wizard (optional): `run_setup_gui.bat`
3. Launch live engine: `run_live.bat`

## Key Modules
- Risk caps (1–3%/trade), mandatory SL, correlation block, daily loss latch.
- Audit logging with HMAC chain (append-only).
- MT5 adapter (login/session, symbol meta); extend for order routing.

## Structure
- chamelefx/managers: engine, guardrails, position sizing
- chamelefx/integrations: mt5_client
- chamelefx/logging: audit (HMAC chain)
- app/cli: runners (live)
- setup_gui.py: minimal Setup Wizard (Auto vs Manual, L0–L5)
- ChameleFX Manager: main app entry after setup (placeholder)

## Operations Notes (added by patch batch)

- Ops routes (`/ops/*`) are gated by default. To enable temporarily:
  1. Create `chamelefx/runtime/admin.key` containing a secret.
  2. Or set in `config.json`: `"ops": {"expose": true, "admin_key": "<SECRET>"}`
  3. Call ops endpoints with header `X-Admin-Key: <SECRET>`.
- API CORS now restricted to `http://127.0.0.1` and `http://localhost` by default.
- UI HTTP calls enforce a default timeout (5s).
