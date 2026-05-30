# Client A

## Spec

### Input

```json

{
  "horizon": {
    "start": "datetime" //eg: 2025-11-03T08:00:00
    "end": "datetime"
  }
  "resources":[
    {
      "id": "id-name" //eg: "Fill-1" or "Fill-2" or "Label-1"
      "capabilities": ["capability"], //eg: "fill"
      "calendar": [
        ["datetime", "datetime"],
        ["datetime", "datetime"],
        ... // More or less scheduled times
      ]
    },
    {
      ... // More resources
    },
  ],
  "changeover_matrix_minutes": {
    "values": {
      "family1->family1": int, //eg: "standard -> premium":20,
      "family1->family2": int,
      ... // more changeover values
    }
  },
  "products": [
    {
      "id": "product-id",
      "family": "family_type", //possible values defined in changeover matrix
      "due": "datetime",
      "route": [
        {"capability": "capability_type", "duration_minutes": int}, // capability_types defined in resources.capabilities
        ... //more steps
      ]
    },
    ... // More products
  ],
  "settings": { //solver settings
    "time_limit_seconds": int,
    "objective_mode": "solver_objective" //eg: min_tardiness
  }
}

```

## Output

```json

{
  "assignments": [
    {
      "product": "products.id",
      "step_index": int, // 1-indexed
      "capability": "capability",
      "resource": "resources.id",
      "start": "datetime",
      "end": "datetime" //start and end times between one of resources.calendar with duration specified by step in products.route.duration_minutes
    },
    {
      // another assignment
    },
    ... // remaning assignments
  ],
  "kpis": {
    "tardiness_minutes": int,
    "changeover_count": int,
    "changeover_minutes": int,
    "makespan_minutes": int,
    "utilization_pct": {
      "resources.id[1]": int,
      "resources.id[2]": int,
      ..., //all resources
    }
  }
}
```

---
## Examples

### Output

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
      "calendar": [
        ["2025-11-03T08:00:00", "2025-11-03T12:00:00"],
        ["2025-11-03T12:30:00", "2025-11-03T16:00:00"]
      ]
    },
    {
      "id": "Fill-2",
      "capabilities": ["fill"],
      "calendar": [
        ["2025-11-03T08:00:00", "2025-11-03T16:00:00"]
      ]
    },
    {
      "id": "Label-1",
      "capabilities": ["label"],
      "calendar": [
        ["2025-11-03T08:00:00", "2025-11-03T16:00:00"]
      ]
    },
    {
      "id": "Pack-1",
      "capabilities": ["pack"],
      "calendar": [
        ["2025-11-03T08:00:00", "2025-11-03T16:00:00"]
      ]
    }
  ],
  "changeover_matrix_minutes": {
    "values": {
      "standard->standard": 0,
      "standard->premium": 20,
      "premium->standard": 20,
      "premium->premium": 0
    }
  },
  "products": [
    {
      "id": "P-100",
      "family": "standard",
      "due": "2025-11-03T12:30:00",
      "route": [
        { "capability": "fill", "duration_minutes": 30 },
        { "capability": "label", "duration_minutes": 20 },
        { "capability": "pack", "duration_minutes": 15 }
      ]
    },
    {
      "id": "P-101",
      "family": "premium",
      "due": "2025-11-03T15:00:00",
      "route": [
        { "capability": "fill", "duration_minutes": 35 },
        { "capability": "label", "duration_minutes": 25 },
        { "capability": "pack", "duration_minutes": 15 }
      ]
    },
    {
      "id": "P-102",
      "family": "standard",
      "due": "2025-11-03T13:30:00",
      "route": [
        { "capability": "fill", "duration_minutes": 25 },
        { "capability": "label", "duration_minutes": 20 }
      ]
    },
    {
      "id": "P-103",
      "family": "premium",
      "due": "2025-11-03T14:00:00",
      "route": [
        { "capability": "fill", "duration_minutes": 30 },
        { "capability": "label", "duration_minutes": 20 },
        { "capability": "pack", "duration_minutes": 15 }
      ]
    }
  ],
  "settings": {
    "time_limit_seconds": 30,
    "objective_mode": "min_tardiness"
  }
}

```

### Output

```json
{
  "assignments": [
    {
      "product": "P-100",
      "step_index": 1,
      "capability": "fill",
      "resource": "Fill-2",
      "start": "2025-11-03T08:00:00",
      "end": "2025-11-03T08:30:00"
    },
    {
      "product": "P-100",
      "step_index": 2,
      "capability": "label",
      "resource": "Label-1",
      "start": "2025-11-03T08:30:00",
      "end": "2025-11-03T08:50:00"
    },
    {
      "product": "P-100",
      "step_index": 3,
      "capability": "pack",
      "resource": "Pack-1",
      "start": "2025-11-03T08:50:00",
      "end": "2025-11-03T09:05:00"
    }
  ],
  "kpis": {
    "tardiness_minutes": 18,
    "changeover_count": 2,
    "changeover_minutes": 40,
    "makespan_minutes": 75,
    "utilization_pct": {
      "Fill-1": 58,
      "Fill-2": 61,
      "Label-1": 49,
      "Pack-1": 23
    }
  }
}
```