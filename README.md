# King of the Curve

Workspace for the King of the Curve gameplay engine.

## Packages

- `packages/engine` - framework-agnostic TypeScript rules engine, mock event
  source, replay store, and simulator for Agent 1 gameplay.

## Commands

```bash
pnpm install
pnpm test
pnpm build
pnpm simulate
```

The shared decay fixture lives at `docs/fixtures/decay.json` and is consumed by
the engine tests to keep TypeScript decay logic locked to the hook approximation.
