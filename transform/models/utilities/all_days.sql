-- A row per calendar day: the time spine the semantic layer joins against.
--
-- Wide enough to cover every season the project could plausibly hold, in both
-- directions. It costs a few thousand rows and removes a whole class of
-- "the metric is missing for weeks nothing happened" problem.

{{ config(materialized='table') }}

select cast(range as date) as date_day
from range(date '2000-01-01', date '2040-01-01', interval 1 day)
