### Constraints

- **Eligibility**: an operation can run only on a resource with the required capability
- **No overlap**: each resource can run at most one operation at a time
- **Precedence**: a product’s route must execute in order
- **Calendars**: each operation must fit fully within one working window of the assigned resource
- **Changeovers**: if two consecutive operations on the same resource belong to different families, insert the required setup time immediately before the later operation
- **Horizon bounds**: all scheduled times must lie within the horizon
- **Non-preemptive**: operations cannot be split across time windows