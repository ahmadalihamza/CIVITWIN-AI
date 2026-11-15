# Dataset import formats

Use `dataset.schema.json` for a complete JSON dataset. CSV imports use a JSON envelope containing `manifest` and `tables`. `manifest` is the same dataset object with the four entity arrays removed. `tables` is an object with the four keys below. Each value is the corresponding CSV file's text, including the header. The manifest's `sha256` must match the equivalent canonical full JSON dataset. See [canonicalization](../demo/README.md).

| Table | Column names |
| --- | --- |
| `nodes` | `id,display_x,display_y,label` |
| `edges` | `from_node,to_node,minutes,direction` |
| `communities` | `id,label,demand_visits_per_week,zone_class,node_id` with optional `population` |
| `sites` | `id,label,type,node_id,capacity_per_week,fixed_cost_pkr,eligible` |

Supply every required column once. Numeric cells use unsigned decimal integers, booleans use `true` or `false`, and a blank population means unknown. An empty edges table contains only the header. Errors identify the table, zero-based data-row index and field where available. The full bundle is limited to 2 MB. Only aggregate data that the steward is authorized to use belongs in an import.
