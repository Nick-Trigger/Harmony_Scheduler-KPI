# Client A request format

This document is the field-by-field reference for the Client A scheduling
problem JSON. It lives next to `client_a.py` because that adapter is the
single source of truth for this wire format - if the schema here drifts
from the Pydantic models in `client_a.py`, the Pydantic models win.

For the response format and full endpoint behavior, see the project root
[ReadMe.md](../../../ReadMe.md#api-documentation) **API documentation** section.

## Top-level shape

```json
{
  "horizon":                   { ... },
  "resources":                 [ ... ],
  "products":                  [ ... ],
  "changeover_matrix_minutes": { ... },
  "settings":                  { ... }
}
```

All five top-level fields are required.

## `horizon`

Defines the planning window. All operations must start at or after `start`
and end at or before `end`.

```json
{
  "horizon": {
    "start": "2025-11-03T08:00:00",
    "end":   "2025-11-03T16:00:00"
  }
}
```

| Field | Type | Required | Description |
|-|-|-|-|
| `start` | datetime | yes | Earliest moment any operation may begin |
| `end` | datetime | yes | Latest moment any operation may end |

Datetimes are ISO 8601 local time strings (no timezone suffix).

## `resources`

Array of machines available during the horizon. Each resource has a set
of capabilities and a calendar describing when it's available.

```json
{
  "resources": [
    {
      "id": "Fill-1",
      "capabilities": ["fill"],
      "calendar": [
        ["2025-11-03T08:00:00", "2025-11-03T12:00:00"],
        ["2025-11-03T12:30:00", "2025-11-03T16:00:00"]
      ]
    }
  ]
}
```

| Field | Type | Required | Description |
|-|-|-|-|
| `id` | string | yes | Unique identifier - referenced in response assignments |
| `capabilities` | string[] | yes | What this resource can do (e.g. `["fill"]` or `["label", "inspect"]`) |
| `calendar` | `[start, end][]` | yes | Working windows during which the resource is available |

**Capabilities** are arbitrary strings - there is no fixed vocabulary. They
must match the `capability` values used in product routes.

**Calendar** is an array of two-element arrays `[start, end]`, each a working
window. Windows may have gaps between them (lunch breaks, maintenance, shift
changes). An operation must fit entirely inside one window - it cannot span
a gap.

## `products`

Array of products to be scheduled. Each product has an ordered route of
operations, each requiring a specific capability.

```json
{
  "products": [
    {
      "id": "P-100",
      "family": "standard",
      "due": "2025-11-03T12:30:00",
      "route": [
        { "capability": "fill",  "duration_minutes": 30 },
        { "capability": "label", "duration_minutes": 20 },
        { "capability": "pack",  "duration_minutes": 15 }
      ]
    }
  ]
}
```

| Field | Type | Required | Description |
|-|-|-|-|
| `id` | string | yes | Unique identifier - referenced in response assignments |
| `family` | string | yes | Family label used for changeover lookups |
| `due` | datetime | yes | Target completion time for the last step |
| `route` | array | yes | Ordered list of operations |

### `route[]`

| Field | Type | Required | Description |
|-|-|-|-|
| `capability` | string | yes | Which capability is required for this step |
| `duration_minutes` | integer > 0 | yes | How long the step takes |

Route order is mandatory - step 2 cannot start until step 1 ends. Operations
are non-preemptive (once started, they run to completion) and indivisible
(cannot be split across working windows).

## `changeover_matrix_minutes`

Setup time required when consecutive operations on the same resource belong
to different families. Setup time is inserted **before** the later operation.

```json
{
  "changeover_matrix_minutes": {
    "values": {
      "standard->standard": 0,
      "standard->premium":  20,
      "premium->standard":  20,
      "premium->premium":   0
    }
  }
}
```

| Field | Type | Required | Description |
|-|-|-|-|
| `values` | object | yes | Map of `"from_family->to_family"` strings to integer minutes |

Keys are strings of the form `"<from>-><to>"` (literal `->` separator).
Values are non-negative integers in minutes.

**Same-family transitions** (`"X->X"`) typically have value `0` but can be
non-zero if your process requires a setup even between same-family products.

**Missing entries** default to `0`. If you want a non-zero setup, you must
include the entry explicitly.

## `settings`

Solver configuration.

```json
{
  "settings": {
    "time_limit_seconds": 30,
    "objective_mode": "min_tardiness"
  }
}
```

| Field | Type | Required | Description |
|-|-|-|-|
| `time_limit_seconds` | integer | yes | Wall-clock budget for the solver |
| `objective_mode` | string | yes | Which objective to optimize. Currently only `"min_tardiness"` is registered |

Unknown `objective_mode` values produce a 400 response with the list of
registered alternatives. To add a new objective, see the **Design notes**
section in the root [`ReadMe.md`](../../../ReadMe.md).

## Full minimal example

A complete request body that exercises every field:

```json
{
  "horizon": {
    "start": "2025-11-03T08:00:00",
    "end": "2025-11-03T16:00:00"
  },
  "resources": [
    {
      "id": "Fill-1",
      "capabilities": ["fill"],
      "calendar": [["2025-11-03T08:00:00", "2025-11-03T16:00:00"]]
    },
    {
      "id": "Label-1",
      "capabilities": ["label"],
      "calendar": [["2025-11-03T08:00:00", "2025-11-03T16:00:00"]]
    }
  ],
  "products": [
    {
      "id": "P-100",
      "family": "standard",
      "due": "2025-11-03T10:00:00",
      "route": [
        { "capability": "fill",  "duration_minutes": 30 },
        { "capability": "label", "duration_minutes": 20 }
      ]
    }
  ],
  "changeover_matrix_minutes": {
    "values": { "standard->standard": 0 }
  },
  "settings": {
    "time_limit_seconds": 10,
    "objective_mode": "min_tardiness"
  }
}
```

Larger fixtures are committed under `backend/tests/example_data/` for
reference.
